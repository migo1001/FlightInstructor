from pathlib import Path

from flight_instructor.event_detector import EventDetector
from flight_instructor.lua_runner import LuaRunner
from flight_instructor.phase_detector import PhaseDetector
from flight_instructor.score_card import ScoreCard


class Session:
    """
    One complete flight session.

    Owns the phase detector, event detector, Lua rule runner, and score card.
    Call update() once per telemetry frame; it returns any violations that were
    newly recorded during that frame so the caller can display them immediately.
    Call reset() to start a fresh session (e.g. after a new flight loads).
    """

    RULE_FILES = ["global.lua", "c172.lua"]

    def __init__(self, rules_dir):
        """
        Initialise and load all rule files from rules_dir.

        rules_dir — path to the directory containing the .lua rule files
        """
        self._rules_dir = Path(rules_dir)
        self._score_card = None
        self._phase_detector = None
        self._event_detector = None
        self._lua_runner = None
        self._start_time = None
        self._end_time = None
        self._reset_internals()

    def reset(self):
        """Discard all session state and prepare for a new flight."""
        self._start_time = None
        self._end_time = None
        self._reset_internals()

    def _reset_internals(self):
        """Recreate all stateful sub-objects."""
        self._score_card = ScoreCard()
        self._phase_detector = PhaseDetector()
        self._event_detector = EventDetector()
        self._lua_runner = LuaRunner()
        for filename in self.RULE_FILES:
            self._lua_runner.load_file(str(self._rules_dir / filename))

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
