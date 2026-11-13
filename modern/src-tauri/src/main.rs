#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde_json::{json, Value};
use std::{
    io::{BufRead, BufReader, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{mpsc, Mutex},
    time::Duration,
};
use tauri::{Emitter, Manager};

struct Backend {
    child: Child,
    input: ChildStdin,
    output: mpsc::Receiver<String>,
}
impl Backend {
    fn start() -> Result<Self, String> {
        let mut cmd;
        if cfg!(debug_assertions) {
            let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
            let python = root.join(if cfg!(windows) {
                ".venv/Scripts/python.exe"
            } else {
                ".venv/bin/python"
            });
            cmd = Command::new(python);
            cmd.current_dir(root).args(["-u", "-m", "modern.backend"]);
        } else {
            let executable = std::env::current_exe().map_err(|e| e.to_string())?;
            cmd = Command::new(
                executable
                    .parent()
                    .ok_or("Missing executable directory")?
                    .join(if cfg!(windows) {
                        "gestimator-backend.exe"
                    } else {
                        "gestimator-backend"
                    }),
            );
        }
        let mut child = cmd
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| e.to_string())?;
        let input = child.stdin.take().ok_or("Missing stdin")?;
        let output = child.stdout.take().ok_or("Missing stdout")?;
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            for line in BufReader::new(output).lines() {
                match line {
                    Ok(line) => {
                        if tx.send(line).is_err() {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        });
        Ok(Self {
            child,
            input,
            output: rx,
        })
    }
    fn request(&mut self, request: &Value, app: &tauri::AppHandle) -> Result<Value, String> {
        writeln!(self.input, "{}", request).map_err(|e| e.to_string())?;
        self.input.flush().map_err(|e| e.to_string())?;
        loop {
            let line = self
                .output
                .recv_timeout(Duration::from_secs(120))
                .map_err(|e| e.to_string())?;
            let response: Value = serde_json::from_str(&line).map_err(|e| e.to_string())?;
            if response["id"] != request["id"] {
                return Err("Backend response ID mismatch".into());
            }
            if response["event"] == "progress" {
                let _ = app.emit("backend-progress", &response);
            } else {
                return Ok(response);
            }
        }
    }
}
impl Drop for Backend {
    fn drop(&mut self) {
        let _ = writeln!(self.input, "{}", json!({"id":"exit","method":"shutdown"}));
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
#[derive(Default)]
struct Bridge(Mutex<Option<Backend>>);
#[tauri::command]
async fn backend_request(app: tauri::AppHandle, request: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = app.state::<Bridge>();
        let mut backend = state.0.lock().map_err(|_|"Backend lock failed")?;
        if backend.is_none(){*backend=Some(Backend::start()?);}
        let response = backend.as_mut().unwrap().request(&request,&app);
        if response.is_err(){*backend=None;return Err("Backend disconnected. Unsaved draft was lost; reconnect and reopen your project copy.".into())}
        response
    }).await.map_err(|e|e.to_string())?
}
struct DesktopTypography(Mutex<Value>);
#[tauri::command]
fn desktop_font(app: tauri::AppHandle) -> Result<Value, String> {
    app.state::<DesktopTypography>()
        .0
        .lock()
        .map(|font| font.clone())
        .map_err(|e| e.to_string())
}
#[cfg(target_os = "linux")]
fn gtk_font(settings: &gtk::Settings) -> Value {
    use gtk::prelude::*;
    let name = settings.gtk_font_name().unwrap_or_else(|| "Sans 11".into());
    let font = gtk::pango::FontDescription::from_string(&name);
    let size = f64::from(font.size()) / f64::from(gtk::pango::SCALE);
    json!({"family":font.family().map(|family|family.to_string()),
           "size":format!("{}{}", size, if font.is_size_absolute(){"px"}else{"pt"})})
}
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Bridge::default())
        .manage(DesktopTypography(Mutex::new(
            json!({"family":null,"size":null}),
        )))
        .setup(|app| {
            app.remove_menu()?;
            #[cfg(target_os = "linux")]
            {
                use gtk::prelude::*;
                if let Some(settings) = gtk::Settings::default() {
                    *app.state::<DesktopTypography>().0.lock().unwrap() = gtk_font(&settings);
                    let handle = app.handle().clone();
                    settings.connect_gtk_font_name_notify(move |settings| {
                        let font = gtk_font(settings);
                        if let Ok(mut current) = handle.state::<DesktopTypography>().0.lock() {
                            *current = font.clone();
                        }
                        let _ = handle.emit("desktop-font", font);
                    });
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_request, desktop_font])
        .build(tauri::generate_context!())
        .expect("Unable to start GEstimator")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Ok(mut backend) = app.state::<Bridge>().0.lock() {
                    *backend = None;
                }
            }
        });
}
