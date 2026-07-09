import sys
from pathlib import Path

from flight_instructor.gui import App
from flight_instructor.session import Session
from flight_instructor.simconnect_source import SimConnectSource


def _rules_dir():
    """
    Resolve the path to the rules/ directory.

    In a PyInstaller --onefile bundle all data files are extracted under
    sys._MEIPASS at runtime; __file__ is not reliable there.  Outside a
    bundle the rules live next to this file inside the package.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "flight_instructor" / "rules"
    return Path(__file__).resolve().parent / "rules"


def main():
    """Entry point."""
    try:
        rules_dir = _rules_dir()
        session = Session(rules_dir)
        source = SimConnectSource()
        app = App(session, source)
        app.mainloop()
        source.disconnect()
    except Exception as exc:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("FlightInstructor - Startup Error", str(exc))


if __name__ == "__main__":
    main()
