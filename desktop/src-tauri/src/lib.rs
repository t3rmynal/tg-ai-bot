// in release the python core ships as a sidecar binary and is spawned here.
// in dev (debug) the core runs separately (python -m tgai), so nothing spawns.

#[cfg(not(debug_assertions))]
use std::sync::Mutex;

#[cfg(not(debug_assertions))]
use tauri::Manager;

#[cfg(not(debug_assertions))]
struct Sidecar(Mutex<Option<tauri_plugin_shell::process::CommandChild>>);

#[cfg(not(debug_assertions))]
fn kill_sidecar(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<Sidecar>() {
        if let Some(child) = state.0.lock().unwrap().take() {
            let _ = child.kill();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init());

    #[cfg(not(debug_assertions))]
    let builder = builder.setup(|app| {
        use tauri_plugin_shell::ShellExt;

        // keep the core's data next to the platform app-data dir
        let data_dir = app.path().app_data_dir().unwrap_or_default();
        let data_arg = data_dir.to_string_lossy().to_string();

        let parent_pid = std::process::id().to_string();
        let sidecar = app
            .shell()
            .sidecar("tgai-server")
            .expect("sidecar tgai-server missing")
            .args(["--data-dir", &data_arg, "--parent-pid", &parent_pid]);
        let (_rx, child) = sidecar.spawn().expect("could not start the core");
        app.manage(Sidecar(Mutex::new(Some(child))));
        Ok(())
    });

    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |_app_handle, _event| {
        // kill the core when the app is exiting so it never orphans
        #[cfg(not(debug_assertions))]
        if let tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit = _event {
            kill_sidecar(_app_handle);
        }
    });
}
