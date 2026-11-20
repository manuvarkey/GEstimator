use std::{path::Path, sync::Mutex};
use tauri::{Emitter, Manager};

#[derive(Default)]
pub struct Pending(Mutex<Queue>);

#[derive(Default)]
struct Queue {
    paths: Vec<String>,
    startup: Vec<std::path::PathBuf>,
}
fn identity(path: &str) -> std::path::PathBuf {
    std::fs::canonicalize(path).unwrap_or_else(|_| path.into())
}
impl Queue {
    fn launch(&mut self, paths: Vec<String>) {
        self.startup = paths.iter().map(|path| identity(path)).collect();
        self.paths.extend(paths);
    }
    // Finder "open document" events only exist on Apple platforms.
    #[cfg(any(target_os = "macos", target_os = "ios", test))]
    fn opened(&mut self, paths: Vec<String>) {
        for path in paths {
            if let Some(index) = self.startup.iter().position(|candidate| *candidate == identity(&path)) {
                self.startup.remove(index);
            } else {
                self.paths.push(path);
            }
        }
    }
    fn take(&mut self) -> Vec<String> {
        // Startup ends when the frontend first consumes requests. Later Finder
        // opens, including the same project, must reach the unsaved guard again.
        self.startup.clear();
        std::mem::take(&mut self.paths)
    }
}
pub fn launch(app: &tauri::AppHandle, paths: Vec<String>) {
    if let Ok(mut queue) = app.state::<Pending>().0.lock() { queue.launch(paths); }
}
#[cfg(any(target_os = "macos", target_os = "ios"))]
pub fn opened(app: &tauri::AppHandle, paths: Vec<String>) {
    if let Ok(mut queue) = app.state::<Pending>().0.lock() { queue.opened(paths); }
    let _ = app.emit("project-open-available", ());
}

pub fn arguments(args: impl IntoIterator<Item = String>, cwd: &Path) -> Vec<String> {
    args.into_iter().filter(|arg| !arg.is_empty() && !arg.starts_with('-') && !arg.contains('\0') && Path::new(arg).extension().is_some_and(|ext| ext.eq_ignore_ascii_case("eproj")))
        .map(|arg| cwd.join(arg).to_string_lossy().into_owned()).collect()
}

pub fn enqueue(app: &tauri::AppHandle, paths: Vec<String>) {
    if paths.is_empty() { return; }
    if let Ok(mut pending) = app.state::<Pending>().0.lock() {
        pending.paths.extend(paths);
    }
    let _ = app.emit("project-open-available", ());
}

#[tauri::command]
pub fn take_project_open_requests(state: tauri::State<'_, Pending>) -> Result<Vec<String>, String> {
    state.0.lock().map(|mut paths| paths.take()).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn startup_duplicate_is_consumed_once_and_reopening_is_allowed() {
        let mut queue = Queue::default();
        queue.launch(vec!["/tmp/a.eproj".into()]);
        queue.opened(vec!["/tmp/a.eproj".into(), "/tmp/b.eproj".into()]);
        assert_eq!(queue.take(), vec!["/tmp/a.eproj", "/tmp/b.eproj"]);
        queue.opened(vec!["/tmp/a.eproj".into()]);
        assert_eq!(queue.take(), vec!["/tmp/a.eproj"]);
    }
    #[test]
    fn cli_only_launch_does_not_suppress_later_finder_open() {
        let mut queue = Queue::default();
        queue.launch(vec!["/tmp/a.eproj".into()]);
        assert_eq!(queue.take(), vec!["/tmp/a.eproj"]);
        queue.opened(vec!["/tmp/a.eproj".into()]);
        assert_eq!(queue.take(), vec!["/tmp/a.eproj"]);
    }
    #[test]
    fn ignores_options_empty_nonprojects_and_nul() {
        let args = ["", "--help", "-psn_0_123", "--project=a.eproj", "notes.txt", "bad\0.eproj"];
        assert!(arguments(args.map(str::to_owned), Path::new("/work")).is_empty());
    }
    #[test]
    fn accepts_missing_projects_for_backend_validation_and_uppercase_extension() {
        let cwd = std::env::current_dir().unwrap();
        assert_eq!(arguments(["missing.EPROJ".to_owned()], &cwd), vec![cwd.join("missing.EPROJ").to_string_lossy().into_owned()]);
    }
    #[test]
    fn preserves_spaces_and_resolves_sender_directory() {
        let cwd = std::env::current_dir().unwrap();
        let absolute = cwd.join("other.eproj");
        assert!(absolute.is_absolute());
        assert_eq!(
            arguments(vec!["--flag".into(), "My estimate.eproj".into(), absolute.to_string_lossy().into_owned()], &cwd),
            vec![cwd.join("My estimate.eproj").to_string_lossy().into_owned(), absolute.to_string_lossy().into_owned()],
        );
    }
}
