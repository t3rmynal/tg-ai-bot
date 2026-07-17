// prevents an extra console window on windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tgai_desktop_lib::run()
}
