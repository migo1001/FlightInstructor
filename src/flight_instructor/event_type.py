from enum import Enum


class EventType(Enum):
    """All discrete flight events that can be fired during a session."""

    # Engine lifecycle
    ENGINE_STARTED = "engine_started"
    ENGINE_STOPPED = "engine_stopped"

    # Ground movement
    TAXI_STARTED = "taxi_started"
    RUNUP_STARTED = "runup_started"
    RUNUP_COMPLETED = "runup_completed"

    # Runway
    RUNWAY_ENTERED = "runway_entered"
    TAKEOFF_ROLL_STARTED = "takeoff_roll_started"

    # Airborne
    LIFTOFF = "liftoff"
    CLIMB_STARTED = "climb_started"
    CRUISE_STARTED = "cruise_started"
    DESCENT_STARTED = "descent_started"
    APPROACH_STARTED = "approach_started"
    TOUCHDOWN = "touchdown"
    TAXI_IN_STARTED = "taxi_in_started"

    # Controls
    PARKING_BRAKE_RELEASED = "parking_brake_released"
    PARKING_BRAKE_SET = "parking_brake_set"

    # Lights
    BEACON_TURNED_ON = "beacon_turned_on"
    BEACON_TURNED_OFF = "beacon_turned_off"
    LANDING_LIGHT_TURNED_ON = "landing_light_turned_on"
    LANDING_LIGHT_TURNED_OFF = "landing_light_turned_off"
    TAXI_LIGHT_TURNED_ON = "taxi_light_turned_on"
    TAXI_LIGHT_TURNED_OFF = "taxi_light_turned_off"
    STROBE_TURNED_ON = "strobe_turned_on"
    STROBE_TURNED_OFF = "strobe_turned_off"
    NAV_LIGHTS_TURNED_ON = "nav_lights_turned_on"
    NAV_LIGHTS_TURNED_OFF = "nav_lights_turned_off"
