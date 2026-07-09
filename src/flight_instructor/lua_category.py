from flight_instructor.score_category import ScoreCategory
from flight_instructor.severity import Severity
from flight_instructor.violation import Violation


class LuaCategory:
    """
    Exposes a single score category to Lua as an object with a malus() method.

    Lua rules call e.g. `safety.malus(10, "Stall warning active.")` to record
    a penalty.  A timestamp is injected each frame by LuaRunner so rule code
    never needs to pass time explicitly.
    """

    def __init__(self, category, score_card):
        """Bind the category and score card that malus() will write to."""
        self._category = category
        self._score_card = score_card
        self._timestamp = 0.0

    def set_timestamp(self, timestamp):
        """Update the timestamp used for violations recorded this frame."""
        self._timestamp = timestamp

    def set_score_card(self, score_card):
        """Swap in a new score card (called at the start of each evaluate())."""
        self._score_card = score_card

    def malus(self, points, description, severity_name=None):
        """
        Record a violation against this category.

        severity_name — optional string: "minor", "moderate", "serious",
                        "critical", or "fatal". Defaults to "moderate".
        """
        self._score_card.add_violation(Violation(
            category=self._category,
            malus=int(points),
            description=str(description),
            timestamp=self._timestamp,
            severity=self._parse_severity(severity_name),
        ))

    def _parse_severity(self, name):
        """Convert a severity name string to a Severity enum value."""
        if name is None:
            return Severity.MODERATE
        mapping = {
            "minor":    Severity.MINOR,
            "moderate": Severity.MODERATE,
            "serious":  Severity.SERIOUS,
            "critical": Severity.CRITICAL,
            "fatal":    Severity.FATAL,
        }
        return mapping.get(str(name).lower(), Severity.MODERATE)
