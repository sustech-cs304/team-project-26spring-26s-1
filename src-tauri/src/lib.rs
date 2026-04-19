use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Mutex,
};
use std::thread::sleep;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, RunEvent,
};
use tauri_plugin_deep_link::DeepLinkExt;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const DEEPLINK_EVENT: &str = "app://deeplink";
const NOTIFICATION_EVENT: &str = "app://notification-request";
const BACKEND_SIDECAR: &str = "agent-backend";
const BACKEND_RUNTIME_DIR: &str = "backend";
const BACKEND_CONFIG_FILE: &str = "config.yaml";
const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8000;
const BACKEND_SHUTDOWN_PATH: &str = "/internal/shutdown";
const BACKEND_SHUTDOWN_HEADER: &str = "X-Backend-Shutdown-Token";
const BACKEND_CONNECT_TIMEOUT: Duration = Duration::from_millis(200);
const BACKEND_STARTUP_TIMEOUT: Duration = Duration::from_secs(4);
const BACKEND_SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(4);
const BACKEND_POLL_INTERVAL: Duration = Duration::from_millis(120);
static BACKEND_TOKEN_COUNTER: AtomicU64 = AtomicU64::new(1);

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

#[derive(Default)]
struct BackendProcessState {
    process: Mutex<Option<ManagedBackendProcess>>,
}

struct ManagedBackendProcess {
    pid: u32,
    child: CommandChild,
    shutdown_token: String,
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

fn backend_socket_addr() -> SocketAddr {
    SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT))
}

fn is_backend_reachable() -> bool {
    TcpStream::connect_timeout(&backend_socket_addr(), BACKEND_CONNECT_TIMEOUT).is_ok()
}

fn wait_for_backend_ready(timeout: Duration) -> bool {
    let start = Instant::now();

    while start.elapsed() < timeout {
        if is_backend_reachable() {
            return true;
        }
        sleep(BACKEND_POLL_INTERVAL);
    }

    is_backend_reachable()
}

fn wait_for_backend_stop(timeout: Duration) -> bool {
    let start = Instant::now();

    while start.elapsed() < timeout {
        if !is_backend_reachable() {
            return true;
        }
        sleep(BACKEND_POLL_INTERVAL);
    }

    !is_backend_reachable()
}

fn decode_backend_output(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).trim_end().to_string()
}

fn generate_backend_shutdown_token() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let counter = BACKEND_TOKEN_COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("{now:x}-{:x}-{:x}", std::process::id(), counter)
}

fn sync_file(source: &Path, target: &Path) -> Result<(), String> {
    let parent = target
        .parent()
        .ok_or_else(|| format!("target path has no parent: {}", target.display()))?;
    fs::create_dir_all(parent).map_err(|error| {
        format!(
            "failed to create parent directory {}: {error}",
            parent.display()
        )
    })?;

    fs::copy(source, target).map_err(|error| {
        format!(
            "failed to copy {} to {}: {error}",
            source.display(),
            target.display()
        )
    })?;

    Ok(())
}

fn backend_dev_seed_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("backend")
}

fn resolve_backend_config_source() -> Result<PathBuf, String> {
    let exe_path = std::env::current_exe()
        .map_err(|error| format!("failed to resolve app executable: {error}"))?;
    let install_dir = exe_path.parent().ok_or_else(|| {
        format!(
            "app executable has no parent directory: {}",
            exe_path.display()
        )
    })?;

    let installed_config = install_dir.join(BACKEND_CONFIG_FILE);
    if installed_config.exists() {
        return Ok(installed_config);
    }

    if cfg!(debug_assertions) {
        let dev_path = backend_dev_seed_dir().join(BACKEND_CONFIG_FILE);
        if dev_path.exists() {
            return Ok(dev_path);
        }
    }

    Err(format!(
        "missing {} beside the installed app executable ({})",
        BACKEND_CONFIG_FILE,
        install_dir.display()
    ))
}

fn ensure_backend_runtime_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let runtime_dir = app
        .path()
        .app_local_data_dir()
        .map_err(|error| format!("failed to resolve app local data dir: {error}"))?
        .join(BACKEND_RUNTIME_DIR);

    for dir in [
        runtime_dir.as_path(),
        runtime_dir.join("assets").as_path(),
        runtime_dir.join("uploads").as_path(),
        runtime_dir.join("workspace").as_path(),
        runtime_dir.join("workspace").join("rag").as_path(),
        runtime_dir.join("workspace").join("skills").as_path(),
        runtime_dir.join("runs").as_path(),
        runtime_dir.join("cron").as_path(),
    ] {
        fs::create_dir_all(dir)
            .map_err(|error| format!("failed to create {}: {error}", dir.display()))?;
    }

    let config_source = resolve_backend_config_source()?;
    sync_file(&config_source, &runtime_dir.join(BACKEND_CONFIG_FILE))?;

    Ok(runtime_dir)
}

fn clear_backend_process_if_pid(app: &AppHandle, pid: u32) {
    if let Ok(mut guard) = app.state::<BackendProcessState>().process.lock() {
        if guard.as_ref().map(|process| process.pid) == Some(pid) {
            *guard = None;
        }
    }
}

fn request_backend_shutdown(shutdown_token: &str) -> Result<(), String> {
    let mut stream = TcpStream::connect_timeout(&backend_socket_addr(), BACKEND_CONNECT_TIMEOUT)
        .map_err(|error| format!("failed to connect to backend shutdown endpoint: {error}"))?;

    let _ = stream.set_read_timeout(Some(BACKEND_SHUTDOWN_TIMEOUT));
    let _ = stream.set_write_timeout(Some(BACKEND_SHUTDOWN_TIMEOUT));

    let request = format!(
        "POST {BACKEND_SHUTDOWN_PATH} HTTP/1.1\r\nHost: {BACKEND_HOST}:{BACKEND_PORT}\r\n{BACKEND_SHUTDOWN_HEADER}: {shutdown_token}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    );

    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("failed to write backend shutdown request: {error}"))?;
    stream
        .flush()
        .map_err(|error| format!("failed to flush backend shutdown request: {error}"))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("failed to read backend shutdown response: {error}"))?;

    let status_line = response.lines().next().unwrap_or_default();
    if status_line.contains(" 200 ") || status_line.contains(" 202 ") {
        return Ok(());
    }

    Err(format!(
        "backend shutdown endpoint returned unexpected response: {status_line}"
    ))
}

fn force_stop_backend_process(process: ManagedBackendProcess) -> Result<(), String> {
    process
        .child
        .kill()
        .map_err(|error| format!("failed to stop agent-backend[{}]: {error}", process.pid))
}

fn stop_backend_sidecar(app: &AppHandle) {
    let process = match app.state::<BackendProcessState>().process.lock() {
        Ok(mut guard) => guard.take(),
        Err(_) => None,
    };

    if let Some(process) = process {
        let pid = process.pid;
        let shutdown_token = process.shutdown_token.clone();

        match request_backend_shutdown(&shutdown_token) {
            Ok(()) => {
                if !wait_for_backend_stop(BACKEND_SHUTDOWN_TIMEOUT) {
                    log::warn!(
                        "agent-backend[{pid}] did not stop after graceful shutdown request; falling back to child kill"
                    );
                    if let Err(error) = force_stop_backend_process(process) {
                        log::warn!("failed to stop agent-backend[{pid}]: {error}");
                    }
                }
            }
            Err(error) => {
                log::warn!(
                    "failed to request graceful shutdown for agent-backend[{pid}]: {error}; falling back to child kill"
                );
                if let Err(kill_error) = force_stop_backend_process(process) {
                    log::warn!("failed to stop agent-backend[{pid}]: {kill_error}");
                }
            }
        }
    }
}

fn start_backend_sidecar(app: &AppHandle) -> Result<(), String> {
    {
        let backend_state = app.state::<BackendProcessState>();
        let guard = backend_state
            .process
            .lock()
            .map_err(|_| "failed to lock backend process state".to_string())?;
        if guard.is_some() {
            return Ok(());
        }
    }

    if is_backend_reachable() {
        log::info!(
            "agent-backend already reachable on http://{}:{}; skipping sidecar startup",
            BACKEND_HOST,
            BACKEND_PORT
        );
        return Ok(());
    }

    let runtime_dir = ensure_backend_runtime_dir(app)?;
    let shutdown_token = generate_backend_shutdown_token();

    let command = app
        .shell()
        .sidecar(BACKEND_SIDECAR)
        .map_err(|error| format!("failed to resolve backend sidecar: {error}"))?
        .current_dir(&runtime_dir)
        .args(vec![
            "agent.main:app".to_string(),
            "--host".to_string(),
            BACKEND_HOST.to_string(),
            "--port".to_string(),
            BACKEND_PORT.to_string(),
            "--shutdown-token".to_string(),
            shutdown_token.clone(),
        ]);

    let (mut events, child) = command
        .spawn()
        .map_err(|error| format!("failed to spawn backend sidecar: {error}"))?;
    let pid = child.pid();

    {
        let backend_state = app.state::<BackendProcessState>();
        let mut guard = backend_state
            .process
            .lock()
            .map_err(|_| "failed to store backend process".to_string())?;

        if guard.is_some() {
            let _ = force_stop_backend_process(ManagedBackendProcess {
                pid,
                child,
                shutdown_token,
            });
            return Ok(());
        }

        *guard = Some(ManagedBackendProcess {
            pid,
            child,
            shutdown_token,
        });
    }

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let line = decode_backend_output(&line);
                    if !line.is_empty() {
                        log::info!("agent-backend[{pid}]: {line}");
                    }
                }
                CommandEvent::Stderr(line) => {
                    let line = decode_backend_output(&line);
                    if !line.is_empty() {
                        log::warn!("agent-backend[{pid}] stderr: {line}");
                    }
                }
                CommandEvent::Error(error) => {
                    log::warn!("agent-backend[{pid}] event error: {error}");
                }
                CommandEvent::Terminated(payload) => {
                    match payload.code {
                        Some(code) => log::warn!("agent-backend[{pid}] exited with code {code}"),
                        None => log::warn!("agent-backend[{pid}] exited"),
                    }
                    clear_backend_process_if_pid(&app_handle, pid);
                }
                _ => {}
            }
        }

        clear_backend_process_if_pid(&app_handle, pid);
    });

    if wait_for_backend_ready(BACKEND_STARTUP_TIMEOUT) {
        log::info!(
            "agent-backend[{pid}] is listening on http://{}:{}",
            BACKEND_HOST,
            BACKEND_PORT
        );
    } else {
        log::warn!(
            "agent-backend[{pid}] did not accept connections on http://{}:{} within {:?}",
            BACKEND_HOST,
            BACKEND_PORT,
            BACKEND_STARTUP_TIMEOUT
        );
    }

    Ok(())
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

fn toggle_main_devtools(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_devtools_open() {
            window.close_devtools();
        } else {
            window.open_devtools();
            let _ = window.set_focus();
        }
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
    let app = tauri::Builder::default()
        .manage(ShortcutThrottle::default())
        .manage(DeeplinkState::default())
        .manage(BackendProcessState::default())
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

            if let Err(err) = start_backend_sidecar(app.handle()) {
                log::warn!("backend sidecar autostart disabled: {err}");
                if cfg!(debug_assertions) {
                    eprintln!("backend sidecar autostart disabled: {err}");
                }
            }

            #[cfg(any(windows, target_os = "linux"))]
            app.deep_link()
                .register_all()
                .map_err(|error| -> Box<dyn std::error::Error> { Box::new(error) })?;

            maybe_handle_cli_deeplink(
                app.handle(),
                &std::env::args().collect::<Vec<_>>(),
                "launch",
            );

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
            let devtools = MenuItemBuilder::new("DevTools")
                .id("toggle-devtools")
                .build(app)?;
            let quit = MenuItemBuilder::new("Quit").id("quit").build(app)?;
            let tray_menu = MenuBuilder::new(app)
                .items(&[&show, &hide, &devtools, &quit])
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
            "toggle-devtools" => toggle_main_devtools(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if matches!(event, RunEvent::Exit) {
            stop_backend_sidecar(app_handle);
        }
    });
}
