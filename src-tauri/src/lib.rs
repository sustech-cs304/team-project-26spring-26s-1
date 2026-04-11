use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    Manager,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
use tauri_plugin_opener::OpenerExt;

#[tauri::command]
fn open_external_link(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let value = url.trim();
    if value.is_empty() {
        return Err("empty url".to_string());
    }

    app.opener()
        .open_url(value, None::<&str>)
        .map_err(|error| error.to_string())
}

#[derive(Default)]
struct ShortcutThrottle {
    last: Mutex<Option<Instant>>,
}

impl ShortcutThrottle {
    fn should_handle(&self, cooldown: Duration) -> bool {
        let now = Instant::now();
        let mut guard = match self.last.lock() {
            Ok(g) => g,
            Err(_) => return true, // poisoned lock: allow handling to continue
        };

        match *guard {
            Some(t) if now.duration_since(t) < cooldown => false,
            _ => {
                *guard = Some(now);
                true
            }
        }
    }
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.center();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn hide_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(ShortcutThrottle::default())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![open_external_link])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let alt_space = Shortcut::new(Some(Modifiers::ALT), Code::KeyQ);
            if let Err(err) =
                app.global_shortcut()
                    .on_shortcut(alt_space, move |_app, _shortcut, _event| {
                        if !_app
                            .state::<ShortcutThrottle>()
                            .should_handle(Duration::from_millis(220))
                        {
                            return;
                        }

                        if let Some(window) = _app.get_webview_window("main") {
                            let visible = window.is_visible().unwrap_or(false);
                            let minimized = window.is_minimized().unwrap_or(false);
                            let focused = window.is_focused().unwrap_or(false);

                            if !visible || minimized || !focused {
                                show_main_window(_app);
                            } else {
                                hide_main_window(_app);
                            }
                        } else {
                            show_main_window(_app);
                        }
                    })
            {
                if cfg!(debug_assertions) {
                    eprintln!("global shortcut disabled: {err}");
                }
            }

            // System tray with basic menu
            let show = MenuItemBuilder::new("Show").id("show").build(app)?;
            let hide = MenuItemBuilder::new("Hide").id("hide").build(app)?;
            let quit = MenuItemBuilder::new("Quit").id("quit").build(app)?;
            let tray_menu = MenuBuilder::new(app)
                .items(&[&show, &hide, &quit])
                .build()?;

            let tray_icon_builder = TrayIconBuilder::new()
                .menu(&tray_menu)
                .show_menu_on_left_click(true);

            let tray_icon_builder = if let Some(icon) = app.default_window_icon() {
                tray_icon_builder.icon(icon.clone())
            } else {
                tray_icon_builder
            };

            tray_icon_builder.build(app)?;

            Ok(())
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_main_window(app),
            "hide" => hide_main_window(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
