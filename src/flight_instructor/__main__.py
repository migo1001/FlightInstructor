import sys
from pathlib import Path

from flight_instructor.gui import App
from flight_instructor.session import Session
from flight_instructor.simconnect_source import SimConnectSource


def _rules_dir():
    """
    Resolve the path to the rules/ directory.

    When packaged with PyInstaller (--onefile), the executable extracts to a
    temporary directory exposed via sys._MEIPASS.  In development the rules/
    directory lives at the project root, three levels above this file.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "rules"
    return Path(__file__).resolve().parent.parent.parent / "rules"


def main():
    """Entry point."""
    rules_dir = _rules_dir()
    session = Session(rules_dir)
    source = SimConnectSource()
    app = App(session, source)
    app.mainloop()
    source.disconnect()


if __name__ == "__main__":
    main()
