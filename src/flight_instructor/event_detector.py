from flight_instructor.event import Event
from flight_instructor.event_type import EventType
from flight_instructor.phase import Phase


class EventDetector:
    """
    Detects discrete flight events by comparing successive state and phase pairs.

    Call update() once per telemetry frame. After each call, self.events contains
    only the events that fired on that exact frame — phase transitions fire on the
    frame the phase changes, state-change events fire on the frame the value flips.
    """

    # Maps (from_phase, to_phase) to the EventType that transition represents.
    _PHASE_TRANSITION_EVENTS = {
        (Phase.COLD_AND_DARK, Phase.PRE_TAXI): EventType.ENGINE_STARTED,
        (Phase.PRE_TAXI, Phase.TAXI_OUT): EventType.TAXI_STARTED,
        (Phase.TAXI_OUT, Phase.RUNUP): EventType.RUNUP_STARTED,
        (Phase.RUNUP, Phase.TAXI_OUT): EventType.RUNUP_COMPLETED,
        (Phase.TAXI_OUT, Phase.LINEUP): EventType.RUNWAY_ENTERED,
        (Phase.RUNUP, Phase.LINEUP): EventType.RUNWAY_ENTERED,
        (Phase.LINEUP, Phase.TAKEOFF_ROLL): EventType.TAKEOFF_ROLL_STARTED,
        (Phase.TAXI_OUT, Phase.TAKEOFF_ROLL): EventType.TAKEOFF_ROLL_STARTED,
        (Phase.TAKEOFF_ROLL, Phase.ROTATION): EventType.LIFTOFF,
        (Phase.ROTATION, Phase.INITIAL_CLIMB): EventType.CLIMB_STARTED,
        (Phase.INITIAL_CLIMB, Phase.CLIMB): EventType.CRUISE_STARTED,
        (Phase.CLIMB, Phase.DESCENT): EventType.DESCENT_STARTED,
        (Phase.CRUISE, Phase.DESCENT): EventType.DESCENT_STARTED,
        (Phase.DESCENT, Phase.APPROACH): EventType.APPROACH_STARTED,
        (Phase.FINAL, Phase.LANDING): EventType.TOUCHDOWN,
        (Phase.ROLLOUT, Phase.TAXI_IN): EventType.TAXI_IN_STARTED,
    }

    # Each entry: (field_name, rising_edge_event, falling_edge_event).
    # rising: False → True.  falling: True → False.  None = no event for that edge.
    _BOOLEAN_STATE_EVENTS = [
        ("engine_running",   None,                          EventType.ENGINE_STOPPED),
        ("parking_brake",    EventType.PARKING_BRAKE_SET,   EventType.PARKING_BRAKE_RELEASED),
        ("beacon_on",        EventType.BEACON_TURNED_ON,    EventType.BEACON_TURNED_OFF),
        ("landing_light_on", EventType.LANDING_LIGHT_TURNED_ON, EventType.LANDING_LIGHT_TURNED_OFF),
        ("taxi_light_on",    EventType.TAXI_LIGHT_TURNED_ON, EventType.TAXI_LIGHT_TURNED_OFF),
        ("strobe_on",        EventType.STROBE_TURNED_ON,    EventType.STROBE_TURNED_OFF),
        ("nav_lights_on",    EventType.NAV_LIGHTS_TURNED_ON, EventType.NAV_LIGHTS_TURNED_OFF),
    ]

    def __init__(self):
        """Initialize with no prior state."""
        self.events = []
        self._prev_state = None
        self._prev_phase = None

    def update(self, state, phase, timestamp):
        """
        Process one telemetry frame. Populates self.events with any events that
        fired this frame. Events from previous frames are discarded.
        """
        self.events = []
        if self._prev_state is not None:
            self._detect_phase_events(state, phase, timestamp)
            self._detect_state_events(state, timestamp)
        self._prev_state = state
        self._prev_phase = phase

    # ------------------------------------------------------------------
    # Internal detectors
    # ------------------------------------------------------------------

    def _detect_phase_events(self, state, phase, timestamp):
        """Fire a phase-transition event if the phase changed and the pair is mapped."""
        if phase == self._prev_phase:
            return
        event_type = self._PHASE_TRANSITION_EVENTS.get((self._prev_phase, phase))
        if event_type is None:
            return
        data = self._get_transition_data(event_type, state)
        self.events.append(Event(event_type, timestamp, **data))

    def _detect_state_events(self, state, timestamp):
        """Fire events for every boolean field that flipped since the last frame."""
        for field, rising_event, falling_event in self._BOOLEAN_STATE_EVENTS:
            prev_val = getattr(self._prev_state, field)
            curr_val = getattr(state, field)
            if curr_val == prev_val:
                continue
            if curr_val and rising_event:
                self.events.append(Event(rising_event, timestamp))
            elif not curr_val and falling_event:
                self.events.append(Event(falling_event, timestamp))

    def _get_transition_data(self, event_type, state):
        """Return extra payload for events that carry context beyond their type."""
        if event_type == EventType.LIFTOFF:
            return {"indicated_airspeed_kt": state.indicated_airspeed_kt}
        return {}
