use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager,
};
use tauri_plugin_deep_link::DeepLinkExt;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
use tauri_plugin_opener::OpenerExt;

const DEEPLINK_EVENT: &str = "app://deeplink";
const NOTIFICATION_EVENT: &str = "app://notification-request";

#[derive(Default)]
struct ShortcutThrottle {
    last: Mutex<Option<Instant>>,
}

impl ShortcutThrottle {
    fn should_handle(&self, cooldown: Duration) -> bool {
        let now = Instant::now();
        let mut guard = match self.last.lock() {
            Ok(g) => g,
            Err(_) => return true,
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

#[derive(Default)]
struct DeeplinkState {
    pending: Mutex<Vec<DeeplinkEvent>>,
    ready: Mutex<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DeeplinkEvent {
    url: String,
    source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct NotificationActionPayload {
    title: String,
    deeplink: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DispatchNotificationPayload {
    title: String,
    message: String,
    level: Option<String>,
    deeplink: Option<String>,
    #[serde(default)]
    actions: Vec<NotificationActionPayload>,
    thread: Option<String>,
    timeout_s: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct DispatchNotificationResponse {
    status: &'static str,
    notification_id: Option<String>,
}

#[tauri::command]
fn open_external_link(app: AppHandle, url: String) -> Result<(), String> {
    let value = url.trim();
    if value.is_empty() {
        return Err("empty url".to_string());
    }

    app.opener()
        .open_url(value, None::<&str>)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn consume_pending_deeplinks(app: AppHandle) -> Result<Vec<DeeplinkEvent>, String> {
    let state = app.state::<DeeplinkState>();
    let mut ready = state
        .ready
        .lock()
        .map_err(|_| "failed to lock deeplink readiness".to_string())?;
    *ready = true;

    let mut guard = state
        .pending
        .lock()
        .map_err(|_| "failed to lock deeplink state".to_string())?;
    let queued = guard.clone();
    guard.clear();
    Ok(queued)
}

#[tauri::command]
fn dispatch_notification(
    app: AppHandle,
    payload: DispatchNotificationPayload,
) -> Result<DispatchNotificationResponse, String> {
    app.emit(NOTIFICATION_EVENT, &payload)
        .map_err(|error| error.to_string())?;

    Ok(DispatchNotificationResponse {
        status: "scheduled",
        notification_id: None,
    })
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.center();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn hide_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

fn is_opencrab_deeplink(url: &str) -> bool {
    url.trim().to_ascii_lowercase().starts_with("opencrab://")
}

fn queue_deeplink(app: &AppHandle, payload: DeeplinkEvent) {
    if let Ok(mut guard) = app.state::<DeeplinkState>().pending.lock() {
        guard.push(payload);
    }
}

fn handle_deeplink(app: &AppHandle, url: impl Into<String>, source: &str) {
    let url = url.into();
    if !is_opencrab_deeplink(&url) {
        return;
    }

    show_main_window(app);

    let payload = DeeplinkEvent {
        url: url.clone(),
        source: source.to_string(),
    };

    let is_ready = app
        .state::<DeeplinkState>()
        .ready
        .lock()
        .map(|guard| *guard)
        .unwrap_or(false);

    if is_ready {
        if app.emit(DEEPLINK_EVENT, &payload).is_err() {
            queue_deeplink(app, payload);
        }
    } else {
        queue_deeplink(app, payload);
    }
}

fn maybe_handle_cli_deeplink(app: &AppHandle, args: &[String], source: &str) {
    for arg in args {
        if is_opencrab_deeplink(arg) {
            handle_deeplink(app, arg.clone(), source);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(ShortcutThrottle::default())
        .manage(DeeplinkState::default())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            maybe_handle_cli_deeplink(app, &argv, "protocol");
        }))
        .invoke_handler(tauri::generate_handler![
            open_external_link,
            consume_pending_deeplinks,
            dispatch_notification
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            #[cfg(any(windows, target_os = "linux"))]
            app.deep_link()
                .register_all()
                .map_err(|error| -> Box<dyn std::error::Error> { Box::new(error) })?;

            maybe_handle_cli_deeplink(app.handle(), &std::env::args().collect::<Vec<_>>(), "launch");

            let app_handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                for url in event.urls() {
                    handle_deeplink(&app_handle, url.to_string(), "protocol");
                }
            });

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
