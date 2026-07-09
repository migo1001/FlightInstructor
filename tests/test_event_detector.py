from flight_instructor.aircraft_state import AircraftState
from flight_instructor.event_detector import EventDetector
from flight_instructor.event_type import EventType
from flight_instructor.phase import Phase
from tests.simulated_telemetry import SimulatedTelemetry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_event(events, event_type):
    """Return True if any event in the list matches the given type."""
    return any(e.event_type == event_type for e in events)


def _get_event(events, event_type):
    """Return the first event matching the given type, or None."""
    for e in events:
        if e.event_type == event_type:
            return e
    return None


def _event_types(events):
    """Return the set of EventType values present in the list."""
    return {e.event_type for e in events}


# ---------------------------------------------------------------------------
# No events without a previous frame
# ---------------------------------------------------------------------------

class TestFirstUpdate:
    def test_no_events_on_first_update(self):
        """The first update has no previous state to compare against."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.cold_and_dark(), Phase.COLD_AND_DARK, 0.0)
        assert detector.events == []

    def test_no_events_when_phase_and_state_unchanged(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        state = s.engine_at_idle()
        detector.update(state, Phase.PRE_TAXI, 0.0)
        detector.update(state, Phase.PRE_TAXI, 0.2)
        assert detector.events == []


# ---------------------------------------------------------------------------
# Phase transition events
# ---------------------------------------------------------------------------

class TestPhaseTransitionEvents:
    def test_engine_started_fires_on_pre_taxi_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.cold_and_dark(), Phase.COLD_AND_DARK, 0.0)
        detector.update(s.engine_at_idle(), Phase.PRE_TAXI, 5.0)
        assert _has_event(detector.events, EventType.ENGINE_STARTED)

    def test_engine_started_fires_only_on_transition_frame(self):
        """ENGINE_STARTED must not repeat on subsequent frames in PRE_TAXI."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.cold_and_dark(), Phase.COLD_AND_DARK, 0.0)
        detector.update(s.engine_at_idle(), Phase.PRE_TAXI, 5.0)
        assert _has_event(detector.events, EventType.ENGINE_STARTED)
        detector.update(s.engine_at_idle(), Phase.PRE_TAXI, 5.2)
        assert not _has_event(detector.events, EventType.ENGINE_STARTED)

    def test_taxi_started_fires_on_taxi_out_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.engine_at_idle(), Phase.PRE_TAXI, 0.0)
        detector.update(s.taxiing(), Phase.TAXI_OUT, 10.0)
        assert _has_event(detector.events, EventType.TAXI_STARTED)

    def test_runup_started_fires_on_runup_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.taxiing(), Phase.TAXI_OUT, 0.0)
        detector.update(s.run_up(), Phase.RUNUP, 20.0)
        assert _has_event(detector.events, EventType.RUNUP_STARTED)

    def test_runup_completed_fires_on_return_to_taxi_out(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.run_up(), Phase.RUNUP, 0.0)
        detector.update(s.taxiing(), Phase.TAXI_OUT, 60.0)
        assert _has_event(detector.events, EventType.RUNUP_COMPLETED)

    def test_runway_entered_fires_on_lineup_from_taxi_out(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.taxiing(), Phase.TAXI_OUT, 0.0)
        detector.update(s.lined_up(), Phase.LINEUP, 30.0)
        assert _has_event(detector.events, EventType.RUNWAY_ENTERED)

    def test_runway_entered_fires_on_lineup_from_runup(self):
        """Run-up area adjacent to runway — entering runway direct from run-up."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.run_up(), Phase.RUNUP, 0.0)
        detector.update(s.lined_up(), Phase.LINEUP, 60.0)
        assert _has_event(detector.events, EventType.RUNWAY_ENTERED)

    def test_takeoff_roll_started_fires_from_lineup(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.lined_up(), Phase.LINEUP, 0.0)
        detector.update(s.takeoff_roll(), Phase.TAKEOFF_ROLL, 30.0)
        assert _has_event(detector.events, EventType.TAKEOFF_ROLL_STARTED)

    def test_takeoff_roll_started_fires_from_taxi_out_rolling_takeoff(self):
        """Rolling takeoff: no lineup stop, power applied directly from taxi."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.taxiing(), Phase.TAXI_OUT, 0.0)
        detector.update(s.takeoff_roll(), Phase.TAKEOFF_ROLL, 30.0)
        assert _has_event(detector.events, EventType.TAKEOFF_ROLL_STARTED)

    def test_liftoff_fires_on_rotation(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.takeoff_roll(), Phase.TAKEOFF_ROLL, 0.0)
        detector.update(s.airborne(), Phase.ROTATION, 30.0)
        assert _has_event(detector.events, EventType.LIFTOFF)

    def test_liftoff_carries_ias_at_rotation(self):
        """LIFTOFF event must record the indicated airspeed at the moment of liftoff."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.takeoff_roll(), Phase.TAKEOFF_ROLL, 0.0)
        airborne = AircraftState(on_ground=False, indicated_airspeed_kt=63.0)
        detector.update(airborne, Phase.ROTATION, 30.0)
        liftoff = _get_event(detector.events, EventType.LIFTOFF)
        assert liftoff is not None
        assert liftoff.data["indicated_airspeed_kt"] == 63.0

    def test_climb_started_fires_on_initial_climb_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.airborne(), Phase.ROTATION, 0.0)
        detector.update(s.climbing(), Phase.INITIAL_CLIMB, 10.0)
        assert _has_event(detector.events, EventType.CLIMB_STARTED)

    def test_cruise_started_fires_on_climb_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.climbing(), Phase.INITIAL_CLIMB, 0.0)
        detector.update(s.climbing(altitude_agl_ft=1200), Phase.CLIMB, 90.0)
        assert _has_event(detector.events, EventType.CRUISE_STARTED)

    def test_no_event_for_unmapped_transition(self):
        """A phase jump with no mapped event and no state change produces nothing."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        # Same state object both times: isolates the phase-transition check from state diffs
        state = s.climbing()
        detector.update(state, Phase.COLD_AND_DARK, 0.0)
        detector.update(state, Phase.CLIMB, 999.0)
        assert detector.events == []


# ---------------------------------------------------------------------------
# State-change events
# ---------------------------------------------------------------------------

class TestStateChangeEvents:
    def test_parking_brake_released_fires(self):
        detector = EventDetector()
        detector.update(AircraftState(parking_brake=True), Phase.PRE_TAXI, 0.0)
        detector.update(AircraftState(parking_brake=False), Phase.PRE_TAXI, 1.0)
        assert _has_event(detector.events, EventType.PARKING_BRAKE_RELEASED)

    def test_parking_brake_set_fires(self):
        detector = EventDetector()
        detector.update(AircraftState(parking_brake=False), Phase.TAXI_OUT, 0.0)
        detector.update(AircraftState(parking_brake=True), Phase.TAXI_OUT, 1.0)
        assert _has_event(detector.events, EventType.PARKING_BRAKE_SET)

    def test_beacon_turned_on_fires(self):
        detector = EventDetector()
        detector.update(AircraftState(beacon_on=False), Phase.COLD_AND_DARK, 0.0)
        detector.update(AircraftState(beacon_on=True), Phase.COLD_AND_DARK, 1.0)
        assert _has_event(detector.events, EventType.BEACON_TURNED_ON)

    def test_beacon_turned_off_fires(self):
        detector = EventDetector()
        detector.update(AircraftState(beacon_on=True), Phase.PRE_TAXI, 0.0)
        detector.update(AircraftState(beacon_on=False), Phase.PRE_TAXI, 1.0)
        assert _has_event(detector.events, EventType.BEACON_TURNED_OFF)

    def test_landing_light_turned_on_fires(self):
        detector = EventDetector()
        detector.update(AircraftState(landing_light_on=False), Phase.TAXI_OUT, 0.0)
        detector.update(AircraftState(landing_light_on=True), Phase.TAXI_OUT, 1.0)
        assert _has_event(detector.events, EventType.LANDING_LIGHT_TURNED_ON)

    def test_landing_light_turned_off_fires(self):
        detector = EventDetector()
        detector.update(AircraftState(landing_light_on=True), Phase.CLIMB, 0.0)
        detector.update(AircraftState(landing_light_on=False), Phase.CLIMB, 1.0)
        assert _has_event(detector.events, EventType.LANDING_LIGHT_TURNED_OFF)

    def test_engine_stopped_fires_when_engine_dies(self):
        detector = EventDetector()
        detector.update(AircraftState(engine_running=True), Phase.CLIMB, 0.0)
        detector.update(AircraftState(engine_running=False), Phase.CLIMB, 1.0)
        assert _has_event(detector.events, EventType.ENGINE_STOPPED)

    def test_no_event_when_boolean_field_unchanged(self):
        detector = EventDetector()
        detector.update(AircraftState(beacon_on=True), Phase.PRE_TAXI, 0.0)
        detector.update(AircraftState(beacon_on=True), Phase.PRE_TAXI, 1.0)
        assert not _has_event(detector.events, EventType.BEACON_TURNED_ON)
        assert not _has_event(detector.events, EventType.BEACON_TURNED_OFF)

    def test_multiple_state_changes_produce_multiple_events(self):
        """Several fields flipping in the same frame all produce events."""
        detector = EventDetector()
        before = AircraftState(parking_brake=True, beacon_on=False)
        after = AircraftState(parking_brake=False, beacon_on=True)
        detector.update(before, Phase.PRE_TAXI, 0.0)
        detector.update(after, Phase.PRE_TAXI, 1.0)
        assert _has_event(detector.events, EventType.PARKING_BRAKE_RELEASED)
        assert _has_event(detector.events, EventType.BEACON_TURNED_ON)
        assert len(detector.events) == 2


# ---------------------------------------------------------------------------
# Phase transition + state change in the same frame
# ---------------------------------------------------------------------------

class TestCombinedEvents:
    def test_phase_and_state_events_fire_in_same_update(self):
        """A phase transition and a state change can both occur in one frame."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        # Engine at idle: beacon on, parking brake set
        detector.update(s.engine_at_idle(), Phase.PRE_TAXI, 0.0)
        # Now taxiing: phase flips to TAXI_OUT and parking brake is released
        detector.update(s.taxiing(), Phase.TAXI_OUT, 10.0)
        assert _has_event(detector.events, EventType.TAXI_STARTED)
        assert _has_event(detector.events, EventType.PARKING_BRAKE_RELEASED)


# ---------------------------------------------------------------------------
# Descent, approach, and landing events
# ---------------------------------------------------------------------------

class TestDescentEvents:
    def test_descent_started_fires_from_climb(self):
        """Direct climb-to-descent transition must emit DESCENT_STARTED."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.climbing(), Phase.CLIMB, 0.0)
        detector.update(s.descending(), Phase.DESCENT, 300.0)
        assert _has_event(detector.events, EventType.DESCENT_STARTED)

    def test_descent_started_fires_from_cruise(self):
        """Cruise-to-descent transition must also emit DESCENT_STARTED."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.cruising(), Phase.CRUISE, 0.0)
        detector.update(s.descending(), Phase.DESCENT, 300.0)
        assert _has_event(detector.events, EventType.DESCENT_STARTED)

    def test_descent_started_fires_only_once(self):
        """DESCENT_STARTED must not repeat on subsequent frames in DESCENT."""
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.cruising(), Phase.CRUISE, 0.0)
        detector.update(s.descending(), Phase.DESCENT, 300.0)
        assert _has_event(detector.events, EventType.DESCENT_STARTED)
        detector.update(s.descending(), Phase.DESCENT, 300.2)
        assert not _has_event(detector.events, EventType.DESCENT_STARTED)


class TestApproachAndLandingEvents:
    def test_approach_started_fires_on_approach_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.descending(), Phase.DESCENT, 0.0)
        detector.update(s.on_approach(), Phase.APPROACH, 120.0)
        assert _has_event(detector.events, EventType.APPROACH_STARTED)

    def test_touchdown_fires_on_landing_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.on_final(), Phase.FINAL, 0.0)
        detector.update(s.touchdown(), Phase.LANDING, 60.0)
        assert _has_event(detector.events, EventType.TOUCHDOWN)

    def test_taxi_in_started_fires_on_taxi_in_entry(self):
        detector = EventDetector()
        s = SimulatedTelemetry()
        detector.update(s.rollout(), Phase.ROLLOUT, 0.0)
        detector.update(s.taxi_in(), Phase.TAXI_IN, 30.0)
        assert _has_event(detector.events, EventType.TAXI_IN_STARTED)
