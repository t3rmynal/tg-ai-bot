// phase a: the python core runs as a separate process (python -m tgai).
// a pyinstaller sidecar spawn can hook into setup() later.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
