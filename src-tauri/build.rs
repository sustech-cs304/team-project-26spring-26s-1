fn main() {
    if std::env::var("PROFILE").as_deref() == Ok("debug") {
        std::env::set_var("TAURI_CONFIG", r#"{"bundle":{"resources":[]}}"#);
    }

    tauri_build::build()
}
