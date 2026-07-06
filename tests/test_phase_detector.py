from flight_instructor.phase import Phase
from flight_instructor.phase_detector import PhaseDetector
from tests.simulated_telemetry import SimulatedTelemetry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance_to_taxi_out(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to TAXI_OUT."""
    telemetry.feed(detector, telemetry.engine_at_idle(), seconds=4)
    telemetry.feed(detector, telemetry.taxiing(), seconds=5)


def _advance_to_takeoff_roll(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to TAKEOFF_ROLL."""
    _advance_to_taxi_out(telemetry, detector)
    telemetry.feed(detector, telemetry.takeoff_roll(), seconds=4)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_starts_cold_and_dark(self):
        detector = PhaseDetector()
        assert detector.phase == Phase.COLD_AND_DARK


# ---------------------------------------------------------------------------
# COLD_AND_DARK → PRE_TAXI  (engine start with hysteresis)
# ---------------------------------------------------------------------------

class TestColdAndDarkToPreTaxi:
    def test_sustained_engine_running_transitions_to_pre_taxi(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=4)
        assert detector.phase == Phase.PRE_TAXI

    def test_brief_engine_running_stays_cold_and_dark(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=1)
        assert detector.phase == Phase.COLD_AND_DARK

    def test_engine_timer_resets_when_engine_stops(self):
        """Non-consecutive engine running must not accumulate toward the threshold."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=1.5)
        telemetry.feed(detector, telemetry.cold_and_dark(), seconds=1)
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=1.5)
        assert detector.phase == Phase.COLD_AND_DARK


# ---------------------------------------------------------------------------
# PRE_TAXI → TAXI_OUT  (movement with hysteresis)
# ---------------------------------------------------------------------------

class TestPreTaxiToTaxiOut:
    def test_sustained_movement_transitions_to_taxi_out(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=4)
        telemetry.feed(detector, telemetry.taxiing(), seconds=5)
        assert detector.phase == Phase.TAXI_OUT

    def test_brief_movement_stays_pre_taxi(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=4)
        telemetry.feed(detector, telemetry.taxiing(), seconds=1)
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=1)
        assert detector.phase == Phase.PRE_TAXI

    def test_taxi_timer_resets_when_aircraft_stops(self):
        """Non-consecutive movement must not accumulate toward the threshold."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=4)
        telemetry.feed(detector, telemetry.taxiing(), seconds=2)
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=1)
        telemetry.feed(detector, telemetry.taxiing(), seconds=2)
        assert detector.phase == Phase.PRE_TAXI


# ---------------------------------------------------------------------------
# TAXI_OUT → RUNUP  (stationary at high RPM)
# ---------------------------------------------------------------------------

class TestTaxiOutToRunup:
    def test_stationary_at_high_rpm_transitions_to_runup(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.run_up(), seconds=5)
        assert detector.phase == Phase.RUNUP

    def test_brief_rpm_spike_stays_taxi_out(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.run_up(), seconds=1)
        assert detector.phase == Phase.TAXI_OUT

    def test_runup_timer_resets_when_rpm_drops(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.run_up(), seconds=2)
        telemetry.feed(detector, telemetry.taxiing(ground_speed_kt=0), seconds=1)
        telemetry.feed(detector, telemetry.run_up(), seconds=2)
        assert detector.phase == Phase.TAXI_OUT


# ---------------------------------------------------------------------------
# RUNUP → TAXI_OUT  (run-up complete, RPM returns to idle)
# ---------------------------------------------------------------------------

class TestRunupToTaxiOut:
    def test_rpm_returning_to_idle_after_runup_transitions_to_taxi_out(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.run_up(), seconds=5)
        assert detector.phase == Phase.RUNUP
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=5)
        assert detector.phase == Phase.TAXI_OUT


# ---------------------------------------------------------------------------
# TAXI_OUT → LINEUP  (entering runway and stopping)
# ---------------------------------------------------------------------------

class TestTaxiOutToLineup:
    def test_entering_runway_and_stopping_transitions_to_lineup(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.lined_up(), seconds=5)
        assert detector.phase == Phase.LINEUP

    def test_stopping_off_runway_does_not_trigger_lineup(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        # Stopped but NOT on runway (e.g. hold-short)
        telemetry.feed(detector, telemetry.engine_at_idle(), seconds=5)
        assert detector.phase == Phase.TAXI_OUT


# ---------------------------------------------------------------------------
# TAXI_OUT / LINEUP → TAKEOFF_ROLL
# ---------------------------------------------------------------------------

class TestToTakeoffRoll:
    def test_full_power_on_runway_transitions_to_takeoff_roll_from_taxi_out(self):
        """Rolling takeoff: aircraft enters runway already at speed and applies power."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.takeoff_roll(), seconds=4)
        assert detector.phase == Phase.TAKEOFF_ROLL

    def test_full_power_on_runway_transitions_to_takeoff_roll_from_lineup(self):
        """Normal takeoff: line up first, then apply full power."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.lined_up(), seconds=5)
        assert detector.phase == Phase.LINEUP
        telemetry.feed(detector, telemetry.takeoff_roll(), seconds=4)
        assert detector.phase == Phase.TAKEOFF_ROLL

    def test_full_power_off_runway_stays_taxi_out(self):
        """Run-up at full power off the runway must not trigger takeoff roll."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.takeoff_roll(on_runway=False), seconds=4)
        assert detector.phase == Phase.TAXI_OUT


# ---------------------------------------------------------------------------
# TAKEOFF_ROLL → ROTATION  (wheels leave the ground)
# ---------------------------------------------------------------------------

class TestTakeoffRollToRotation:
    def test_leaving_ground_transitions_to_rotation(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_takeoff_roll(telemetry, detector)
        telemetry.feed(detector, telemetry.airborne(), seconds=2)
        assert detector.phase == Phase.ROTATION

    def test_brief_airborne_bump_stays_takeoff_roll(self):
        """A single frame off-ground (bump) must not flip to ROTATION."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_takeoff_roll(telemetry, detector)
        telemetry.feed(detector, telemetry.airborne(), seconds=0.1)
        telemetry.feed(detector, telemetry.takeoff_roll(), seconds=1)
        assert detector.phase == Phase.TAKEOFF_ROLL


# ---------------------------------------------------------------------------
# ROTATION → INITIAL_CLIMB  (altitude and climb rate established)
# ---------------------------------------------------------------------------

class TestRotationToInitialClimb:
    def test_altitude_and_climb_rate_establishes_initial_climb(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_takeoff_roll(telemetry, detector)
        telemetry.feed(detector, telemetry.airborne(), seconds=2)
        assert detector.phase == Phase.ROTATION
        telemetry.feed(detector, telemetry.climbing(), seconds=4)
        assert detector.phase == Phase.INITIAL_CLIMB

    def test_low_altitude_airborne_stays_rotation(self):
        """Must not leave ROTATION until altitude and climb rate are both established."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_takeoff_roll(telemetry, detector)
        telemetry.feed(detector, telemetry.airborne(), seconds=2)
        # Still very low and barely climbing
        telemetry.feed(detector, telemetry.airborne(altitude_agl_ft=30, vertical_speed_fpm=100), seconds=4)
        assert detector.phase == Phase.ROTATION


# ---------------------------------------------------------------------------
# INITIAL_CLIMB → CLIMB
# ---------------------------------------------------------------------------

class TestInitialClimbToClimb:
    def test_passing_1000_ft_transitions_to_climb(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_takeoff_roll(telemetry, detector)
        telemetry.feed(detector, telemetry.airborne(), seconds=2)
        telemetry.feed(detector, telemetry.climbing(), seconds=4)
        assert detector.phase == Phase.INITIAL_CLIMB
        telemetry.feed(detector, telemetry.climbing(altitude_agl_ft=1200), seconds=5)
        assert detector.phase == Phase.CLIMB
