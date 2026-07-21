import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext

from flight_instructor.facilities import FacilitiesClient
from flight_instructor.location import LocationService
from flight_instructor.phase import Phase
from flight_instructor.score_category import ScoreCategory


_CATEGORY_COLORS = {
    ScoreCategory.SAFETY:           "#FF4444",
    ScoreCategory.PROCEDURES:       "#FFD700",
    ScoreCategory.AIRCRAFT_HANDLING:"#FF8C00",
    ScoreCategory.AIRCRAFT_CARE:    "#00BFFF",
    ScoreCategory.NAVIGATION:       "#7CFC00",
}

_CATEGORY_LABELS = {
    ScoreCategory.SAFETY:           "SAFETY",
    ScoreCategory.PROCEDURES:       "PROCEDURES",
    ScoreCategory.AIRCRAFT_HANDLING:"HANDLING",
    ScoreCategory.AIRCRAFT_CARE:    "CARE",
    ScoreCategory.NAVIGATION:       "NAVIGATION",
}

_BG            = "#1A1A2E"
_BG_PANEL      = "#16213E"
_FG_DIM        = "#6B7280"
_FG_PHASE      = "#93C5FD"
_FG_SCORE      = "#F9FAFB"
_FG_STATUS     = "#6EE7B7"
_FG_STATUS_ERR = "#FCA5A5"
_FG_CONN_LOG   = "#4B5563"


class App(tk.Tk):
    """
    Main application window.

    Polls the SimConnect source at POLL_MS intervals using tkinter's after().
    New violations are appended to the scrolling log as they occur.
    Phase and score are refreshed every poll.
    """

    POLL_MS       = 200   # 5 Hz
    RETRY_MS      = 3000  # retry connection every 3 s when MSFS not running
    WINDOW_TITLE  = "FlightInstructor"
    WINDOW_SIZE   = "720x480"

    def __init__(self, session, source):
        """
        Create the window.

        session — Session instance (already loaded with rules)
        source  — SimConnectSource instance (not yet connected)
        """
        super().__init__()
        self._session       = session
        self._source        = source
        self._facilities    = FacilitiesClient()
        self._location      = LocationService(facilities=self._facilities)
        self._retry_count   = 0
        self._connected     = False

        self.title(self.WINDOW_TITLE)
        self.geometry(self.WINDOW_SIZE)
        self.resizable(True, True)
        self.configure(bg=_BG)

        self._build_ui()
        self.after(0, self._try_connect)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build all widgets."""
        self._build_header()
        self._build_location_bar()
        self._build_weather_bar()
        self._build_log()
        self._build_status()

    def _build_header(self):
        """Top bar: phase on the left, connection dot + score on the right."""
        frame = tk.Frame(self, bg=_BG_PANEL, padx=16, pady=10)
        frame.pack(fill=tk.X, side=tk.TOP)

        mono      = tkfont.Font(family="Consolas", size=13)
        mono_bold = tkfont.Font(family="Consolas", size=13, weight="bold")

        self._phase_var = tk.StringVar(value="Phase: -")
        tk.Label(
            frame,
            textvariable=self._phase_var,
            fg=_FG_PHASE, bg=_BG_PANEL,
            font=mono, anchor="w",
        ).pack(side=tk.LEFT)

        self._score_var = tk.StringVar(value="Score: 100")
        tk.Label(
            frame,
            textvariable=self._score_var,
            fg=_FG_SCORE, bg=_BG_PANEL,
            font=mono_bold, anchor="e",
        ).pack(side=tk.RIGHT)

        # Coloured dot: green = connected, red = disconnected
        self._conn_dot = tk.Label(
            frame,
            text="  MSFS",
            fg=_FG_STATUS_ERR, bg=_BG_PANEL,
            font=mono, anchor="e",
        )
        self._conn_dot.pack(side=tk.RIGHT, padx=(0, 16))

    def _build_location_bar(self):
        """Slim bar showing the aircraft's current position (airport, runway, etc.)."""
        frame = tk.Frame(self, bg=_BG_PANEL, padx=16, pady=4)
        frame.pack(fill=tk.X, side=tk.TOP)

        self._location_var = tk.StringVar(value="")
        tk.Label(
            frame,
            textvariable=self._location_var,
            fg=_FG_DIM, bg=_BG_PANEL,
            font=tkfont.Font(family="Consolas", size=11),
            anchor="w",
        ).pack(side=tk.LEFT)

    def _build_weather_bar(self):
        """Slim bar showing wind, visibility, and active runway."""
        frame = tk.Frame(self, bg=_BG_PANEL, padx=16, pady=4)
        frame.pack(fill=tk.X, side=tk.TOP)

        self._weather_var = tk.StringVar(value="")
        tk.Label(
            frame,
            textvariable=self._weather_var,
            fg=_FG_DIM, bg=_BG_PANEL,
            font=tkfont.Font(family="Consolas", size=11),
            anchor="w",
        ).pack(side=tk.LEFT)

    def _build_log(self):
        """Scrolling log in the middle — violations and connection events."""
        frame = tk.Frame(self, bg=_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._log = scrolledtext.ScrolledText(
            frame,
            bg=_BG, fg=_FG_DIM,
            font=tkfont.Font(family="Consolas", size=11),
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
            padx=14, pady=10,
        )
        self._log.pack(fill=tk.BOTH, expand=True)

        for category, colour in _CATEGORY_COLORS.items():
            self._log.tag_config(category.name, foreground=colour)
        self._log.tag_config("time",         foreground=_FG_DIM)
        self._log.tag_config("malus",        foreground="#F87171")
        self._log.tag_config("desc",         foreground=_FG_SCORE)
        self._log.tag_config("conn_ok",      foreground=_FG_STATUS)
        self._log.tag_config("conn_err",     foreground=_FG_STATUS_ERR)
        self._log.tag_config("conn_dim",     foreground=_FG_CONN_LOG)
        self._log.tag_config("summary_sep",  foreground="#374151")
        self._log.tag_config("summary_head", foreground="#93C5FD")
        self._log.tag_config("summary_val",  foreground=_FG_SCORE)
        self._log.tag_config("summary_good", foreground=_FG_STATUS)
        self._log.tag_config("summary_bad",  foreground=_FG_STATUS_ERR)

    def _build_status(self):
        """Bottom status bar — last connection message."""
        frame = tk.Frame(self, bg=_BG_PANEL, padx=16, pady=6)
        frame.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_var = tk.StringVar(value="Searching for MSFS 2020...")
        self._status_label = tk.Label(
            frame,
            textvariable=self._status_var,
            fg=_FG_STATUS_ERR, bg=_BG_PANEL,
            font=tkfont.Font(family="Consolas", size=10),
            anchor="w",
        )
        self._status_label.pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _try_connect(self):
        """Attempt SimConnect connection; schedule retry on failure."""
        self._retry_count += 1
        self._append_conn(f"[Attempt {self._retry_count}] Connecting to MSFS 2020...", "conn_dim")
        try:
            self._source.connect()
            self._set_connected(True)
            self._append_conn("[OK] Connected to MSFS 2020.", "conn_ok")
            self._facilities.connect()
            self.after(self.POLL_MS, self._poll)
        except Exception as exc:
            self._set_connected(False)
            self._append_conn(f"[FAIL] {exc}", "conn_err")
            self.after(self.RETRY_MS, self._try_connect)

    def _set_connected(self, ok):
        """Update connection dot colour and status bar."""
        self._connected = ok
        colour = _FG_STATUS if ok else _FG_STATUS_ERR
        self._conn_dot.configure(fg=colour)
        text   = "Connected to MSFS 2020" if ok else "Not connected - retrying every 3 s"
        self._status_var.set(text)
        self._status_label.configure(fg=colour)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    # Phases that are worth logging when the snap detects them on first frame
    _SNAP_LOG_PHASES = frozenset({
        Phase.LINEUP, Phase.TAKEOFF_ROLL,
        Phase.INITIAL_CLIMB, Phase.CLIMB, Phase.CRUISE,
        Phase.DESCENT, Phase.APPROACH, Phase.FINAL,
        Phase.TAXI_OUT,
    })

    def _poll(self):
        """Read one telemetry frame and process it."""
        state = self._source.read()

        if state is None:
            self._set_connected(False)
            self._append_conn("[FAIL] Connection lost.", "conn_err")
            self._facilities.disconnect()
            if self._session.has_data:
                self._session.mark_ended(time.monotonic())
                self._show_summary()
                self._session.reset()
            self.after(self.RETRY_MS, self._try_connect)
            return

        first_frame = not self._session.has_data
        new_violations = self._session.update(state, time.monotonic())
        for v in new_violations:
            self._append_violation(v)

        if first_frame and self._session.phase in self._SNAP_LOG_PHASES:
            phase_name = self._session.phase.value.replace("_", " ").title()
            self._append_conn(f"[Detected] Starting in {phase_name}", "conn_ok")

        if self._session.phase == Phase.SHUTDOWN:
            self._session.mark_ended(time.monotonic())
            self._show_summary()
            self._session.reset()

        self._update_header(state)
        self.after(self.POLL_MS, self._poll)

    # ------------------------------------------------------------------
    # UI updates
    # ------------------------------------------------------------------

    def _update_header(self, state=None):
        """Refresh phase label, score, location bar, and weather bar."""
        phase_name = self._session.phase.value.replace("_", " ").title()
        self._phase_var.set(f"Phase: {phase_name}")
        self._score_var.set(f"Score: {self._session.score}")
        if state is not None:
            self._location_var.set(self._location.describe(state))
            self._weather_var.set(self._format_weather(state))

    def _format_weather(self, state):
        """Build the weather bar string from wind, visibility, and active runway."""
        wind_spd = state.wind_speed_kt
        wind_dir = state.wind_direction_deg

        if wind_spd < 3:
            wind_str = "Wind Calm"
        else:
            wind_str = f"Wind {wind_dir:03.0f}° / {wind_spd:.0f} kt"

        parts = [wind_str]

        if state.visibility_m < 8000:
            km = state.visibility_m / 1000.0
            parts.append(f"{km:.1f} km vis")

        icao = self._location._cached_icao
        if icao and wind_spd >= 3 and self._facilities.has_data(icao):
            rwys = self._facilities.active_runways(icao, wind_dir, wind_spd)
            if rwys:
                rwy_str = ", ".join(r.designator for r in rwys)
                parts.append(f"Rwy {rwy_str}")

        return "   ·   ".join(parts)

    def _append_conn(self, message, tag):
        """Append a connection status line to the log."""
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, f"{message}\n", tag)
        self._log.configure(state=tk.DISABLED)
        self._log.see(tk.END)

    def _append_violation(self, violation):
        """Append one violation to the scrolling log with per-category colour."""
        session_time  = violation.timestamp
        category_label = _CATEGORY_LABELS.get(violation.category, violation.category.name)
        colour_tag    = violation.category.name

        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, f"[{session_time:7.1f}s]  ", "time")
        self._log.insert(tk.END, f"{category_label:<12}", colour_tag)
        self._log.insert(tk.END, f"  -{violation.malus:<3}  ", "malus")
        self._log.insert(tk.END, f"{violation.description}\n", "desc")
        self._log.configure(state=tk.DISABLED)
        self._log.see(tk.END)

    def _show_summary(self):
        """Render a flight debrief block in the scrolling log."""
        session      = self._session
        score_card   = session.score_card
        violations   = score_card.violations()
        score        = score_card.score()
        duration     = session.flight_duration or 0
        phase_name   = session.phase.value.replace("_", " ").title()

        minutes, seconds = divmod(int(duration), 60)
        hours, minutes   = divmod(minutes, 60)
        dur_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

        sep = "─" * 48

        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, f"\n{sep}\n", "summary_sep")
        self._log.insert(tk.END, "  FLIGHT SUMMARY\n", "summary_head")
        self._log.insert(tk.END, f"{sep}\n", "summary_sep")

        score_tag = "summary_good" if score >= 80 else "summary_bad"
        self._log.insert(tk.END, f"  Score:   ", "time")
        self._log.insert(tk.END, f"{score}", score_tag)
        self._log.insert(tk.END, " / 100", "time")
        self._log.insert(tk.END, f"    Phase: {phase_name}    Time: {dur_str}\n", "time")

        active_caps = score_card.active_caps()
        if active_caps:
            cap_str = ", ".join(f"cap {c.max_score}" for c in active_caps)
            self._log.insert(tk.END, f"  Caps:    {cap_str}\n", "summary_bad")

        if violations:
            total_malus = sum(v.malus for v in violations)
            self._log.insert(tk.END, f"\n  VIOLATIONS  ({len(violations)} total, -{total_malus} pts)\n", "summary_head")
            for v in violations:
                label = _CATEGORY_LABELS.get(v.category, v.category.name)
                tag   = v.category.name
                self._log.insert(tk.END, f"  [{v.timestamp:7.1f}s]  ", "time")
                self._log.insert(tk.END, f"{label:<12}", tag)
                self._log.insert(tk.END, f"  -{v.malus:<3}  ", "malus")
                self._log.insert(tk.END, f"{v.description}\n", "desc")

            self._log.insert(tk.END, f"\n  BY CATEGORY\n", "summary_head")
            for category in ScoreCategory:
                cat_score = score_card.category_score(category)
                label     = _CATEGORY_LABELS.get(category, category.name)
                tag       = "summary_good" if cat_score >= 80 else "summary_bad"
                self._log.insert(tk.END, f"  {label:<14}", "time")
                self._log.insert(tk.END, f"{cat_score}\n", tag)
        else:
            self._log.insert(tk.END, "\n  No violations recorded. Clean flight!\n", "summary_good")

        self._log.insert(tk.END, f"{sep}\n\n", "summary_sep")
        self._log.configure(state=tk.DISABLED)
        self._log.see(tk.END)
