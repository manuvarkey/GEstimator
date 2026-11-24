//! Text clipboard commands shared by the ribbon and editor shortcuts.

use tauri::AppHandle;

#[cfg(not(target_os = "linux"))]
use tauri_plugin_clipboard_manager::ClipboardExt;

#[cfg(target_os = "linux")]
async fn on_gtk_clipboard<T: Send + 'static>(
    app: AppHandle,
    action: impl FnOnce(gtk::Clipboard, tauri::async_runtime::Sender<Result<T, String>>) + Send + 'static,
) -> Result<T, String> {
    let (sender, mut receiver) = tauri::async_runtime::channel(1);
    app.run_on_main_thread(move || {
        // GTK uses the same display and input seat as WebKit. The independent
        // data-control clipboard can be unavailable or stale inside Wayland Flatpaks.
        if let Some(clipboard) = gtk::gdk::Display::default().and_then(|display| gtk::Clipboard::default(&display)) {
            action(clipboard, sender);
        } else {
            let _ = sender.try_send(Err("System clipboard unavailable".into()));
        }
    })
    .map_err(|error| error.to_string())?;
    receiver
        .recv()
        .await
        .ok_or_else(|| "System clipboard request closed".to_string())?
}

#[tauri::command]
pub async fn read_clipboard_text(app: AppHandle) -> Result<String, String> {
    #[cfg(target_os = "linux")]
    return on_gtk_clipboard(app, |clipboard, sender| {
        clipboard.request_text(move |_, text| {
            let _ = sender.try_send(
                text.map(str::to_owned)
                    .ok_or_else(|| "System clipboard has no text".into()),
            );
        });
    })
    .await;

    #[cfg(not(target_os = "linux"))]
    app.clipboard().read_text().map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn write_clipboard_text(app: AppHandle, text: String) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    return on_gtk_clipboard(app, move |clipboard, sender| {
        clipboard.set_text(&text);
        let _ = sender.try_send(Ok(()));
    })
    .await;

    #[cfg(not(target_os = "linux"))]
    app.clipboard().write_text(text).map_err(|error| error.to_string())
}
