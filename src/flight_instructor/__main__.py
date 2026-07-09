from pathlib import Path

from flight_instructor.gui import App
from flight_instructor.session import Session
from flight_instructor.simconnect_source import SimConnectSource


def _rules_dir():
    """
    Resolve the path to the rules/ directory.

    The rules live inside the package (flight_instructor/rules/), so they are
    found correctly whether running from source, a wheel install, or a
    PyInstaller bundle.
    """
    return Path(__file__).resolve().parent / "rules"


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
