from enum import Enum


class Phase(Enum):
    """All possible flight phases from cold-and-dark through securing the aircraft."""

    COLD_AND_DARK = "cold_and_dark"
    PRE_TAXI = "pre_taxi"
    TAXI_OUT = "taxi_out"
    RUNUP = "runup"
    HOLD_SHORT = "hold_short"
    LINEUP = "lineup"
    TAKEOFF_ROLL = "takeoff_roll"
    ROTATION = "rotation"
    INITIAL_CLIMB = "initial_climb"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"
    APPROACH = "approach"
    FINAL = "final"
    LANDING = "landing"
    ROLLOUT = "rollout"
    TAXI_IN = "taxi_in"
    PARKING = "parking"
    SHUTDOWN = "shutdown"
    SECURED = "secured"
