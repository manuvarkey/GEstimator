"""GEstimator package. GTK is loaded only for legacy application entry points."""

def __getattr__(name):
    if name in {"MainApp", "MainWindow"}:
        from . import gtk_app
        return getattr(gtk_app, name)
    raise AttributeError(name)
