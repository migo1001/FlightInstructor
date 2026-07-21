import logging
from pathlib import Path

from flight_instructor.event_detector import EventDetector
from flight_instructor.lua_runner import LuaRunner
from flight_instructor.phase_detector import PhaseDetector
from flight_instructor.score_card import ScoreCard

log = logging.getLogger(__name__)


class Session:
    """
    One complete flight session.

    Owns the phase detector, event detector, Lua rule runner, and score card.
    Call update() once per telemetry frame; it returns any violations that were
    newly recorded during that frame so the caller can display them immediately.
    Call reset() to start a fresh session (e.g. after a new flight loads).

    Aircraft profile auto-detection
    --------------------------------
    On the very first telemetry frame the TITLE SimVar is used to find a Lua
    profile file whose stem appears in the aircraft title (case-insensitive).
    For example, a title containing "172" or "skyhawk" matches c172.lua.
    global.lua is always loaded regardless of aircraft type.
    """

    GLOBAL_RULES = "global.lua"

    def __init__(self, rules_dir):
        """
        Initialise and load the global rule file from rules_dir.

        rules_dir — path to the directory containing the .lua rule files.
        Aircraft-specific rules are loaded automatically on the first frame.
        """
        self._rules_dir = Path(rules_dir)
        self._score_card = None
        self._phase_detector = None
        self._event_detector = None
        self._lua_runner = None
        self._start_time = None
        self._end_time = None
        self._profile_loaded = False
        self._reset_internals()

    def reset(self):
        """Discard all session state and prepare for a new flight."""
        self._start_time = None
        self._end_time = None
        self._profile_loaded = False
        self._reset_internals()

    def _reset_internals(self):
        """Recreate all stateful sub-objects and load the global rule file."""
        self._score_card = ScoreCard()
        self._phase_detector = PhaseDetector()
        self._event_detector = EventDetector()
        self._lua_runner = LuaRunner()
        self._lua_runner.load_file(str(self._rules_dir / self.GLOBAL_RULES))

    @property
    def has_data(self):
        """True once at least one telemetry frame has been processed."""
        return self._start_time is not None

    @property
    def flight_duration(self):
        """Elapsed flight time in seconds, or None if no data yet."""
        if self._start_time is None:
            return None
        end = self._end_time if self._end_time is not None else self._start_time
        return end - self._start_time

    def mark_ended(self, wall_time):
        """Record the wall time when the flight connection was lost."""
        if self._start_time is not None:
            self._end_time = wall_time

    def update(self, state, wall_time):
        """
        Process one telemetry frame.

        Returns a list of Violation objects that were newly added this frame.
        The list is empty for the vast majority of frames.
        """
        if self._start_time is None:
            self._start_time = wall_time
            self._load_aircraft_profile(state.aircraft_title)

        self._end_time = wall_time
        timestamp = wall_time - self._start_time

        before = len(self._score_card.violations())

        self._phase_detector.update(state, timestamp)
        self._event_detector.update(state, self._phase_detector.phase, timestamp)

        events = [e.event_type for e in self._event_detector.events]
        self._lua_runner.evaluate(
            state,
            self._phase_detector.phase,
            events,
            self._score_card,
            timestamp,
        )

        return self._score_card.violations()[before:]

    # ------------------------------------------------------------------
    # Aircraft profile loading
    # ------------------------------------------------------------------

    def _load_aircraft_profile(self, aircraft_title):
        """
        Find and load the Lua profile file that best matches aircraft_title.

        Looks for any non-global .lua file whose stem appears as a substring
        of the lowercased aircraft title.  Skips gracefully if no match or
        if the file cannot be loaded.
        """
        if self._profile_loaded:
            return
        self._profile_loaded = True

        profile_path = self._detect_profile(aircraft_title)
        if profile_path is None:
            log.info("Session: no aircraft profile matched '%s'; using global rules only.", aircraft_title)
            return

        log.info("Session: loading aircraft profile '%s' for '%s'.", profile_path.name, aircraft_title)
        try:
            self._lua_runner.load_file(str(profile_path))
        except Exception as exc:
            log.warning("Session: failed to load profile '%s': %s", profile_path.name, exc)
            return

        config = self._lua_runner.get_phase_config()
        if config:
            self._phase_detector.configure(config)
            log.info("Session: phase thresholds configured from profile: %s", config)

    def _detect_profile(self, aircraft_title):
        """
        Return the Path to the best matching profile .lua file, or None.

        Matching: the file stem must appear as a substring of the lowercased
        aircraft title (e.g. "c172" matches "Cessna Skyhawk C172").
        """
        title_lower = aircraft_title.lower()
        for lua_file in sorted(self._rules_dir.glob("*.lua")):
            if lua_file.stem == "global":
                continue
            if lua_file.stem in title_lower:
                return lua_file
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def phase(self):
        """Current flight phase as a Phase enum value."""
        return self._phase_detector.phase

    @property
    def score(self):
        """Current overall score (0-100)."""
        return self._score_card.score()

    @property
    def score_card(self):
        """Full ScoreCard for post-flight debrief."""
        return self._score_card
