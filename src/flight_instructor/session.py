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
    """

    RULE_FILES = ["global.lua", "c172.lua"]

    def __init__(self, rules_dir):
        """
        Initialise and load all rule files from rules_dir.

        rules_dir — path to the directory containing the .lua rule files
        """
        self._score_card = ScoreCard()
        self._phase_detector = PhaseDetector()
        self._event_detector = EventDetector()
        self._lua_runner = LuaRunner()
        self._start_time = None

        rules_dir = Path(rules_dir)
        for filename in self.RULE_FILES:
            self._lua_runner.load_file(str(rules_dir / filename))

    def update(self, state, wall_time):
        """
        Process one telemetry frame.

        Returns a list of Violation objects that were newly added this frame.
        The list is empty for the vast majority of frames.
        """
        if self._start_time is None:
            self._start_time = wall_time
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
