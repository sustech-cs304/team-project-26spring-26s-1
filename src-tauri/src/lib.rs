use std::fs;
use std::io::{BufRead, BufReader, Read};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::thread::sleep;
use std::time::{Duration, Instant};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use serde::{Deserialize, Serialize};
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    path::BaseDirectory,
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, RunEvent,
};
use tauri_plugin_deep_link::DeepLinkExt;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
use tauri_plugin_opener::OpenerExt;

const DEEPLINK_EVENT: &str = "app://deeplink";
const NOTIFICATION_EVENT: &str = "app://notification-request";

const BACKEND_RUNTIME_DIR: &str = "backend";
const BACKEND_CONFIG_FILE: &str = "config.yaml";
const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8000;
const BACKEND_CONNECT_TIMEOUT: Duration = Duration::from_millis(200);
const BACKEND_STARTUP_TIMEOUT: Duration = Duration::from_secs(12);
const BACKEND_POLL_INTERVAL: Duration = Duration::from_millis(120);

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

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
    child: Child,
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

fn sync_file_if_missing(source: &Path, target: &Path) -> Result<(), String> {
    if target.exists() {
        return Ok(());
    }

    sync_file(source, target)
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

#[cfg(target_os = "windows")]
fn python_candidates(resource_dir: &Path) -> Vec<PathBuf> {
    let runtime = resource_dir.join("python-runtime");
    vec![
        runtime.join("python.exe"),
        runtime.join("Scripts").join("python.exe"),
        runtime.join(".venv").join("Scripts").join("python.exe"),
    ]
}

#[cfg(not(target_os = "windows"))]
fn python_candidates(resource_dir: &Path) -> Vec<PathBuf> {
    let runtime = resource_dir.join("python-runtime");
    vec![
        runtime.join("bin").join("python"),
        runtime.join("python"),
        runtime.join(".venv").join("bin").join("python"),
    ]
}

fn resolve_python_executable(resource_dir: &Path) -> Result<PathBuf, String> {
    let candidates = python_candidates(resource_dir);

    for path in &candidates {
        if path.exists() {
            return Ok(path.clone());
        }
    }

    Err(format!(
        "missing python executable; checked: {}",
        candidates
            .iter()
            .map(|p| p.display().to_string())
            .collect::<Vec<_>>()
            .join(", ")
    ))
}

fn has_backend_resources(resource_dir: &Path) -> bool {
    resolve_python_executable(resource_dir).is_ok()
}

fn resolve_backend_resource_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let mut candidates = Vec::new();

    if let Ok(path) = app.path().resolve("", BaseDirectory::Resource) {
        candidates.push(path.clone());
        candidates.push(path.join("resources"));
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    candidates.push(manifest_dir.join("resources"));
    candidates.push(manifest_dir.join("..").join("src-tauri").join("resources"));

    for path in &candidates {
        if has_backend_resources(path) {
            return Ok(path.clone());
        }
    }

    Err(format!(
        "missing backend resources; checked: {}",
        candidates
            .iter()
            .map(|p| p.display().to_string())
            .collect::<Vec<_>>()
            .join(", ")
    ))
}

fn app_exe_dir() -> Option<PathBuf> {
    std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
}

fn app_exe_config_path() -> Option<PathBuf> {
    app_exe_dir()
        .map(|dir| dir.join(BACKEND_CONFIG_FILE))
        .filter(|path| path.exists())
}

fn resolve_backend_config_source(app: &AppHandle, resource_dir: &Path) -> Option<PathBuf> {
    let mut candidates = Vec::new();

    if let Some(path) = app_exe_config_path() {
        candidates.push(path);
    }

    if let Ok(path) = app
        .path()
        .resolve(BACKEND_CONFIG_FILE, BaseDirectory::Resource)
    {
        candidates.push(path);
    }

    candidates.push(resource_dir.join(BACKEND_CONFIG_FILE));
    candidates.push(resource_dir.join("config.default.yaml"));

    candidates.into_iter().find(|path| path.exists())
}

fn ensure_backend_runtime_dir(app: &AppHandle, resource_dir: &Path) -> Result<PathBuf, String> {
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
        runtime_dir.join("logs").as_path(),
        runtime_dir.join("cache").as_path(),
    ] {
        fs::create_dir_all(dir)
            .map_err(|error| format!("failed to create {}: {error}", dir.display()))?;
    }

    let target_config = runtime_dir.join(BACKEND_CONFIG_FILE);

    if let Some(config_source) = app_exe_config_path() {
        sync_file(&config_source, &target_config)?;
    } else if let Some(config_source) = resolve_backend_config_source(app, resource_dir) {
        sync_file_if_missing(&config_source, &target_config)?;
    } else {
        log::info!(
            "no bundled backend config found; agent-backend will create {} in {}",
            BACKEND_CONFIG_FILE,
            runtime_dir.display()
        );
    }

    Ok(runtime_dir)
}

fn force_stop_backend_process(mut process: ManagedBackendProcess) -> Result<(), String> {
    if let Ok(Some(_status)) = process.child.try_wait() {
        return Ok(());
    }

    process
        .child
        .kill()
        .map_err(|error| format!("failed to stop agent-backend[{}]: {error}", process.pid))?;

    let _ = process.child.wait();
    Ok(())
}

fn stop_backend_sidecar(app: &AppHandle) {
    let process = match app.state::<BackendProcessState>().process.lock() {
        Ok(mut guard) => guard.take(),
        Err(_) => None,
    };

    if let Some(process) = process {
        let pid = process.pid;
        if let Err(error) = force_stop_backend_process(process) {
            log::warn!("failed to stop agent-backend[{pid}]: {error}");
        }
    }
}

fn spawn_backend_output_logger<R>(reader: R, pid: u32, is_stderr: bool)
where
    R: Read + Send + 'static,
{
    thread::spawn(move || {
        let reader = BufReader::new(reader);

        for line in reader.lines() {
            match line {
                Ok(line) => {
                    let line = line.trim_end().to_string();
                    if line.is_empty() {
                        continue;
                    }

                    if is_stderr {
                        log::warn!("agent-backend[{pid}] stderr: {line}");
                    } else {
                        log::info!("agent-backend[{pid}]: {line}");
                    }
                }
                Err(error) => {
                    log::warn!("agent-backend[{pid}] output read error: {error}");
                    break;
                }
            }
        }
    });
}

fn spawn_backend_exit_watcher(app: AppHandle, pid: u32) {
    thread::spawn(move || loop {
        sleep(Duration::from_millis(500));

        let should_stop = {
            let backend_state = app.state::<BackendProcessState>();
            let mut guard = match backend_state.process.lock() {
                Ok(guard) => guard,
                Err(_) => return,
            };

            let Some(process) = guard.as_mut() else {
                return;
            };

            if process.pid != pid {
                return;
            }

            match process.child.try_wait() {
                Ok(Some(status)) => {
                    log::warn!("agent-backend[{pid}] exited with status {status}");
                    *guard = None;
                    true
                }
                Ok(None) => false,
                Err(error) => {
                    log::warn!("agent-backend[{pid}] exit watcher error: {error}");
                    *guard = None;
                    true
                }
            }
        };

        if should_stop {
            break;
        }
    });
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
            "agent-backend already reachable on http://{}:{}; skipping startup",
            BACKEND_HOST,
            BACKEND_PORT
        );
        return Ok(());
    }

    let resource_dir = resolve_backend_resource_dir(app)?;
    let runtime_dir = ensure_backend_runtime_dir(app, &resource_dir)?;
    let python = resolve_python_executable(&resource_dir)?;

    log::info!("starting agent-backend with python: {}", python.display());
    log::info!("agent-backend module: agent.main");
    log::info!("agent-backend working dir: {}", runtime_dir.display());
    log::info!("agent-backend resource dir: {}", resource_dir.display());

    let mut command = Command::new(&python);
    command
        .arg("-m")
        .arg("agent.main")
        .arg("--host")
        .arg(BACKEND_HOST)
        .arg("--port")
        .arg(BACKEND_PORT.to_string())
        .current_dir(&runtime_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONUTF8", "1")
        .env("PYTHONNOUSERSITE", "1")
        .env("AGENT_DATA_DIR", &runtime_dir)
        .env("AGENT_RESOURCE_DIR", &resource_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);

    let mut child = command
        .spawn()
        .map_err(|error| format!("failed to spawn python backend: {error}"))?;

    let pid = child.id();

    if let Some(stdout) = child.stdout.take() {
        spawn_backend_output_logger(stdout, pid, false);
    }

    if let Some(stderr) = child.stderr.take() {
        spawn_backend_output_logger(stderr, pid, true);
    }

    {
        let backend_state = app.state::<BackendProcessState>();
        let mut guard = backend_state
            .process
            .lock()
            .map_err(|_| "failed to store backend process".to_string())?;

        if guard.is_some() {
            let _ = force_stop_backend_process(ManagedBackendProcess { pid, child });
            return Ok(());
        }

        *guard = Some(ManagedBackendProcess { pid, child });
    }

    spawn_backend_exit_watcher(app.clone(), pid);

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
                log::warn!("backend autostart disabled: {err}");
                if cfg!(debug_assertions) {
                    eprintln!("backend autostart disabled: {err}");
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
