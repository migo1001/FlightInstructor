from enum import Enum


class Severity(Enum):
    """Qualitative severity of a scoring violation, used for reporting."""

    MINOR = "minor"          # -1 to -3
    MODERATE = "moderate"    # -4 to -8
    SERIOUS = "serious"      # -10 to -20
    CRITICAL = "critical"    # -25 to -50 or score cap
    FATAL = "fatal"          # score 0
