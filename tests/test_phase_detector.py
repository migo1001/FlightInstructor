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


def _advance_to_rotation(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to ROTATION."""
    _advance_to_takeoff_roll(telemetry, detector)
    telemetry.feed(detector, telemetry.airborne(), seconds=2)


def _advance_to_initial_climb(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to INITIAL_CLIMB."""
    _advance_to_rotation(telemetry, detector)
    telemetry.feed(detector, telemetry.climbing(), seconds=4)


def _advance_to_climb(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to CLIMB."""
    _advance_to_initial_climb(telemetry, detector)
    telemetry.feed(detector, telemetry.climbing(altitude_agl_ft=1200), seconds=5)


def _advance_to_cruise(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to CRUISE."""
    _advance_to_climb(telemetry, detector)
    telemetry.feed(detector, telemetry.cruising(), seconds=7)


def _advance_to_descent(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to DESCENT."""
    _advance_to_cruise(telemetry, detector)
    telemetry.feed(detector, telemetry.descending(), seconds=7)


def _advance_to_approach(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to APPROACH."""
    _advance_to_descent(telemetry, detector)
    telemetry.feed(detector, telemetry.on_approach(), seconds=5)


def _advance_to_final(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to FINAL."""
    _advance_to_approach(telemetry, detector)
    telemetry.feed(detector, telemetry.on_final(), seconds=4)


def _advance_to_landing(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to LANDING (just entered, not yet ROLLOUT)."""
    _advance_to_final(telemetry, detector)
    # 0.8 s = 4 frames; touchdown enters LANDING at frame 4 (~0.6 s held),
    # leaving only one frame in LANDING — not enough to trigger ROLLOUT (needs 1.0 s).
    telemetry.feed(detector, telemetry.touchdown(), seconds=0.8)


def _advance_to_rollout(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to ROLLOUT."""
    _advance_to_landing(telemetry, detector)
    telemetry.feed(detector, telemetry.rollout(), seconds=2)


def _advance_to_taxi_in(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to TAXI_IN."""
    _advance_to_rollout(telemetry, detector)
    # GS=0 satisfies rollout→taxi_in (needs GS < 2 kt for 2 s).
    # 4 s gives 20 frames; TAXI_IN entered at ~2 s, leaving ~2 s in TAXI_IN,
    # which is less than the 3 s needed for PARKING.
    telemetry.feed(detector, telemetry.rollout(ground_speed_kt=0), seconds=4)


def _advance_to_parking(telemetry, detector):
    """Drive the detector from COLD_AND_DARK to PARKING."""
    _advance_to_taxi_in(telemetry, detector)
    telemetry.feed(detector, telemetry.taxi_in(ground_speed_kt=0), seconds=5)


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

    def test_full_power_high_speed_triggers_takeoff_roll_regardless_of_runway_simvar(self):
        """High throttle at 40 kt on the ground means takeoff roll even if on_runway is False.
        ON_ANY_RUNWAY is unreliable; speed + throttle is the deciding signal."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_out(telemetry, detector)
        telemetry.feed(detector, telemetry.takeoff_roll(on_runway=False), seconds=4)
        assert detector.phase == Phase.TAKEOFF_ROLL


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


# ---------------------------------------------------------------------------
# CLIMB → CRUISE  (level-off)
# ---------------------------------------------------------------------------

class TestClimbToCruise:
    def test_level_flight_transitions_to_cruise(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_climb(telemetry, detector)
        telemetry.feed(detector, telemetry.cruising(), seconds=7)
        assert detector.phase == Phase.CRUISE

    def test_brief_level_flight_stays_climb(self):
        """Level-off must persist for LEVEL_OFF_SECONDS before transitioning."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_climb(telemetry, detector)
        telemetry.feed(detector, telemetry.cruising(), seconds=2)
        assert detector.phase == Phase.CLIMB

    def test_level_off_timer_resets_when_climbing_resumes(self):
        """Interrupted level-off must restart the hold timer."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_climb(telemetry, detector)
        telemetry.feed(detector, telemetry.cruising(), seconds=3)
        telemetry.feed(detector, telemetry.climbing(altitude_agl_ft=1200), seconds=2)
        telemetry.feed(detector, telemetry.cruising(), seconds=3)
        assert detector.phase == Phase.CLIMB


# ---------------------------------------------------------------------------
# CLIMB → DESCENT  (direct, skipping CRUISE)
# ---------------------------------------------------------------------------

class TestClimbToDescent:
    def test_sustained_descent_from_climb_transitions_to_descent(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_climb(telemetry, detector)
        telemetry.feed(detector, telemetry.descending(), seconds=7)
        assert detector.phase == Phase.DESCENT


# ---------------------------------------------------------------------------
# CRUISE → DESCENT
# ---------------------------------------------------------------------------

class TestCruiseToDescent:
    def test_sustained_descent_from_cruise_transitions_to_descent(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_cruise(telemetry, detector)
        telemetry.feed(detector, telemetry.descending(), seconds=7)
        assert detector.phase == Phase.DESCENT

    def test_brief_descent_stays_cruise(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_cruise(telemetry, detector)
        telemetry.feed(detector, telemetry.descending(), seconds=2)
        assert detector.phase == Phase.CRUISE


# ---------------------------------------------------------------------------
# DESCENT → APPROACH
# ---------------------------------------------------------------------------

class TestDescentToApproach:
    def test_below_approach_altitude_transitions_to_approach(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_descent(telemetry, detector)
        telemetry.feed(detector, telemetry.on_approach(), seconds=5)
        assert detector.phase == Phase.APPROACH

    def test_brief_drop_stays_descent(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_descent(telemetry, detector)
        telemetry.feed(detector, telemetry.on_approach(), seconds=1)
        assert detector.phase == Phase.DESCENT


# ---------------------------------------------------------------------------
# APPROACH → FINAL
# ---------------------------------------------------------------------------

class TestApproachToFinal:
    def test_below_final_altitude_transitions_to_final(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_approach(telemetry, detector)
        telemetry.feed(detector, telemetry.on_final(), seconds=4)
        assert detector.phase == Phase.FINAL

    def test_brief_drop_stays_approach(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_approach(telemetry, detector)
        telemetry.feed(detector, telemetry.on_final(), seconds=0.5)
        assert detector.phase == Phase.APPROACH


# ---------------------------------------------------------------------------
# FINAL → LANDING  (touchdown)
# ---------------------------------------------------------------------------

class TestFinalToLanding:
    def test_touchdown_transitions_to_landing(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_final(telemetry, detector)
        telemetry.feed(detector, telemetry.touchdown(), seconds=0.8)
        assert detector.phase == Phase.LANDING

    def test_brief_ground_contact_stays_final(self):
        """A single frame on ground (brief bump) must not flip to LANDING."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_final(telemetry, detector)
        telemetry.feed(detector, telemetry.touchdown(), seconds=0.1)
        telemetry.feed(detector, telemetry.on_final(), seconds=1)
        assert detector.phase == Phase.FINAL


# ---------------------------------------------------------------------------
# LANDING → ROLLOUT
# ---------------------------------------------------------------------------

class TestLandingToRollout:
    def test_ias_below_60kt_transitions_to_rollout(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_landing(telemetry, detector)
        telemetry.feed(detector, telemetry.rollout(), seconds=2)
        assert detector.phase == Phase.ROLLOUT


# ---------------------------------------------------------------------------
# ROLLOUT → TAXI_IN
# ---------------------------------------------------------------------------

class TestRolloutToTaxiIn:
    def test_speed_below_taxi_threshold_transitions_to_taxi_in(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_rollout(telemetry, detector)
        telemetry.feed(detector, telemetry.rollout(ground_speed_kt=0), seconds=4)
        assert detector.phase == Phase.TAXI_IN

    def test_still_moving_stays_rollout(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_rollout(telemetry, detector)
        telemetry.feed(detector, telemetry.rollout(ground_speed_kt=15), seconds=4)
        assert detector.phase == Phase.ROLLOUT


# ---------------------------------------------------------------------------
# TAXI_IN → PARKING
# ---------------------------------------------------------------------------

class TestTaxiInToParking:
    def test_essentially_stopped_transitions_to_parking(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_in(telemetry, detector)
        telemetry.feed(detector, telemetry.taxi_in(ground_speed_kt=0), seconds=5)
        assert detector.phase == Phase.PARKING

    def test_still_moving_stays_taxi_in(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_taxi_in(telemetry, detector)
        telemetry.feed(detector, telemetry.taxi_in(ground_speed_kt=5), seconds=5)
        assert detector.phase == Phase.TAXI_IN


# ---------------------------------------------------------------------------
# PARKING → SHUTDOWN
# ---------------------------------------------------------------------------

class TestParkingToShutdown:
    def test_engine_off_transitions_to_shutdown(self):
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_parking(telemetry, detector)
        telemetry.feed(detector, telemetry.engine_shutdown(), seconds=4)
        assert detector.phase == Phase.SHUTDOWN

    def test_brief_engine_off_stays_parking(self):
        """Engine must be off for SHUTDOWN_SECONDS before transition."""
        telemetry = SimulatedTelemetry()
        detector = PhaseDetector()
        _advance_to_parking(telemetry, detector)
        telemetry.feed(detector, telemetry.engine_shutdown(), seconds=0.5)
        assert detector.phase == Phase.PARKING
