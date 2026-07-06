from flight_instructor.phase import Phase


class PhaseDetector:
    """
    Tracks the current flight phase by evaluating state transitions with hysteresis.

    Each transition requires its triggering condition to hold for a minimum
    duration before the phase changes. This prevents noisy telemetry samples
    from causing false phase flips. Timers are keyed by transition name and
    reset whenever the condition clears before the threshold is reached.
    """

    # Thresholds — all durations in seconds, speeds in knots, RPM as engine_rpm
    ENGINE_RUNNING_SECONDS = 2.0
    TAXI_SPEED_KT = 2.0
    TAXI_ENTRY_SECONDS = 3.0
    RUNUP_RPM = 1500.0
    RUNUP_ENTRY_SECONDS = 3.0
    RUNUP_EXIT_RPM = 1000.0
    RUNUP_EXIT_SECONDS = 3.0
    LINEUP_SPEED_KT = 10.0
    LINEUP_ENTRY_SECONDS = 3.0
    TAKEOFF_THROTTLE_PCT = 70.0
    TAKEOFF_SPEED_KT = 10.0
    TAKEOFF_ROLL_SECONDS = 2.0
    AIRBORNE_SECONDS = 0.5
    CLIMB_AGL_FT = 100.0
    CLIMB_VS_FPM = 200.0
    INITIAL_CLIMB_SECONDS = 2.0
    CRUISE_AGL_FT = 1000.0
    CRUISE_ENTRY_SECONDS = 3.0

    def __init__(self):
        """Initialize with the aircraft assumed to be cold and dark."""
        self.phase = Phase.COLD_AND_DARK
        self._timers = {}

    def update(self, state, timestamp):
        """Process one telemetry sample and advance the phase state machine if warranted."""
        handlers = {
            Phase.COLD_AND_DARK: self._from_cold_and_dark,
            Phase.PRE_TAXI: self._from_pre_taxi,
            Phase.TAXI_OUT: self._from_taxi_out,
            Phase.RUNUP: self._from_runup,
            Phase.LINEUP: self._from_lineup,
            Phase.TAKEOFF_ROLL: self._from_takeoff_roll,
            Phase.ROTATION: self._from_rotation,
            Phase.INITIAL_CLIMB: self._from_initial_climb,
        }
        handler = handlers.get(self.phase)
        if handler:
            handler(state, timestamp)

    # ------------------------------------------------------------------
    # Per-phase transition handlers
    # ------------------------------------------------------------------

    def _from_cold_and_dark(self, state, timestamp):
        """Cold and dark: wait for engine to stabilise at idle."""
        self._transition_if_held(
            "engine_running",
            state.engine_running,
            Phase.PRE_TAXI,
            self.ENGINE_RUNNING_SECONDS,
            timestamp,
        )

    def _from_pre_taxi(self, state, timestamp):
        """Pre-taxi: wait for sustained ground movement."""
        self._transition_if_held(
            "moving",
            state.ground_speed_kt > self.TAXI_SPEED_KT,
            Phase.TAXI_OUT,
            self.TAXI_ENTRY_SECONDS,
            timestamp,
        )

    def _from_taxi_out(self, state, timestamp):
        """Taxi out: check for takeoff roll (highest priority), then lineup, then run-up."""
        takeoff_conditions = (
            state.on_runway
            and state.throttle_pct >= self.TAKEOFF_THROTTLE_PCT
            and state.ground_speed_kt > self.TAKEOFF_SPEED_KT
        )
        if self._transition_if_held("takeoff_roll", takeoff_conditions, Phase.TAKEOFF_ROLL, self.TAKEOFF_ROLL_SECONDS, timestamp):
            return

        lineup_conditions = (
            state.on_runway
            and state.ground_speed_kt < self.LINEUP_SPEED_KT
        )
        if self._transition_if_held("lineup", lineup_conditions, Phase.LINEUP, self.LINEUP_ENTRY_SECONDS, timestamp):
            return

        runup_conditions = (
            not state.on_runway
            and state.ground_speed_kt < self.TAXI_SPEED_KT
            and state.engine_rpm >= self.RUNUP_RPM
        )
        self._transition_if_held("runup", runup_conditions, Phase.RUNUP, self.RUNUP_ENTRY_SECONDS, timestamp)

    def _from_runup(self, state, timestamp):
        """Run-up: return to taxi out when RPM drops back to idle range."""
        runup_complete = (
            state.engine_rpm < self.RUNUP_EXIT_RPM
            and state.ground_speed_kt < self.TAXI_SPEED_KT
        )
        self._transition_if_held("runup_complete", runup_complete, Phase.TAXI_OUT, self.RUNUP_EXIT_SECONDS, timestamp)

    def _from_lineup(self, state, timestamp):
        """Lined up on runway: wait for takeoff power and acceleration."""
        takeoff_conditions = (
            state.on_runway
            and state.throttle_pct >= self.TAKEOFF_THROTTLE_PCT
            and state.ground_speed_kt > self.TAKEOFF_SPEED_KT
        )
        self._transition_if_held("takeoff_roll", takeoff_conditions, Phase.TAKEOFF_ROLL, self.TAKEOFF_ROLL_SECONDS, timestamp)

    def _from_takeoff_roll(self, state, timestamp):
        """Takeoff roll: transition to rotation the moment wheels leave the ground."""
        self._transition_if_held(
            "airborne",
            not state.on_ground,
            Phase.ROTATION,
            self.AIRBORNE_SECONDS,
            timestamp,
        )

    def _from_rotation(self, state, timestamp):
        """Rotation: confirm climb by requiring altitude and positive vertical speed."""
        climbing = (
            state.altitude_agl_ft > self.CLIMB_AGL_FT
            and state.vertical_speed_fpm > self.CLIMB_VS_FPM
        )
        self._transition_if_held("climbing", climbing, Phase.INITIAL_CLIMB, self.INITIAL_CLIMB_SECONDS, timestamp)

    def _from_initial_climb(self, state, timestamp):
        """Initial climb: transition to cruise climb above 1000 ft AGL."""
        self._transition_if_held(
            "cruise_altitude",
            state.altitude_agl_ft > self.CRUISE_AGL_FT,
            Phase.CLIMB,
            self.CRUISE_ENTRY_SECONDS,
            timestamp,
        )

    # ------------------------------------------------------------------
    # Hysteresis primitive
    # ------------------------------------------------------------------

    def _transition_if_held(self, key, condition, target_phase, required_seconds, timestamp):
        """
        Transition to target_phase only if condition has been continuously true
        for at least required_seconds. Returns True if a transition occurred.
        """
        if condition:
            if key not in self._timers:
                self._timers[key] = timestamp
            elif timestamp - self._timers[key] >= required_seconds:
                self._enter_phase(target_phase)
                return True
        else:
            self._timers.pop(key, None)
        return False

    def _enter_phase(self, phase):
        """Switch to a new phase and clear all pending transition timers."""
        self.phase = phase
        self._timers.clear()
