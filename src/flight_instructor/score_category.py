from enum import Enum


class ScoreCategory(Enum):
    """The five scoring dimensions tracked independently in every flight report."""

    PROCEDURES = "procedures"
    SAFETY = "safety"
    AIRCRAFT_HANDLING = "aircraft_handling"
    AIRCRAFT_CARE = "aircraft_care"
    NAVIGATION = "navigation"
