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
    LEVEL_OFF_VS_FPM = 200.0
    LEVEL_OFF_SECONDS = 5.0
    DESCENT_VS_FPM = -300.0
    DESCENT_ENTRY_SECONDS = 5.0
    APPROACH_AGL_FT = 2000.0
    APPROACH_ENTRY_SECONDS = 3.0
    FINAL_AGL_FT = 500.0
    FINAL_ENTRY_SECONDS = 2.0
    TOUCHDOWN_SECONDS = 0.5
    ROLLOUT_IAS_KT = 60.0
    ROLLOUT_ENTRY_SECONDS = 1.0
    TAXI_IN_ENTRY_SECONDS = 2.0
    PARKING_SPEED_KT = 1.0
    PARKING_ENTRY_SECONDS = 3.0
    SHUTDOWN_SECONDS = 2.0

    # Keys that Lua profile files may override via configure_phases().
    # Maps the Lua snake_case key to the Python class-attribute name.
    _CONFIGURABLE = {
        "runup_rpm":            "RUNUP_RPM",
        "runup_exit_rpm":       "RUNUP_EXIT_RPM",
        "takeoff_throttle_pct": "TAKEOFF_THROTTLE_PCT",
        "rollout_ias_kt":       "ROLLOUT_IAS_KT",
        "cruise_agl_ft":        "CRUISE_AGL_FT",
        "final_agl_ft":         "FINAL_AGL_FT",
        "approach_agl_ft":      "APPROACH_AGL_FT",
    }

    def __init__(self):
        """Initialize with the aircraft assumed to be cold and dark."""
        self.phase = Phase.COLD_AND_DARK
        self._timers = {}
        self._snapped = False

    def configure(self, config):
        """
        Apply aircraft-specific threshold overrides supplied by a Lua profile.

        config — dict of snake_case keys (matching _CONFIGURABLE) to float values.
        Only keys present in _CONFIGURABLE are applied; unknown keys are ignored.
        """
        for lua_key, py_attr in self._CONFIGURABLE.items():
            if lua_key in config:
                setattr(self, py_attr, float(config[lua_key]))

    def update(self, state, timestamp):
        """Process one telemetry sample and advance the phase state machine if warranted."""
        if not self._snapped:
            self._snap_to_initial_phase(state)
            self._snapped = True

        handlers = {
            Phase.COLD_AND_DARK: self._from_cold_and_dark,
            Phase.PRE_TAXI: self._from_pre_taxi,
            Phase.TAXI_OUT: self._from_taxi_out,
            Phase.RUNUP: self._from_runup,
            Phase.LINEUP: self._from_lineup,
            Phase.TAKEOFF_ROLL: self._from_takeoff_roll,
            Phase.ROTATION: self._from_rotation,
            Phase.INITIAL_CLIMB: self._from_initial_climb,
            Phase.CLIMB: self._from_climb,
            Phase.CRUISE: self._from_cruise,
            Phase.DESCENT: self._from_descent,
            Phase.APPROACH: self._from_approach,
            Phase.FINAL: self._from_final,
            Phase.LANDING: self._from_landing,
            Phase.ROLLOUT: self._from_rollout,
            Phase.TAXI_IN: self._from_taxi_in,
            Phase.PARKING: self._from_parking,
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
        # Guard: if we somehow lifted off while still in TAXI_OUT (e.g. ON_ANY_RUNWAY
        # SimVar was unreliable and TAKEOFF_ROLL was never detected), recover by
        # jumping straight to ROTATION so the airborne chain can continue.
        if self._transition_if_held(
            "airborne_from_taxi", not state.on_ground, Phase.ROTATION, self.AIRBORNE_SECONDS, timestamp
        ):
            return

        # Takeoff roll: high throttle + accelerating on the ground.
        # Deliberately does not require on_runway — the SimVar is unreliable.
        takeoff_conditions = (
            state.on_ground
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
        if self._transition_if_held(
            "airborne_from_lineup", not state.on_ground, Phase.ROTATION, self.AIRBORNE_SECONDS, timestamp
        ):
            return
        # Same as TAXI_OUT: do not require on_runway here.
        takeoff_conditions = (
            state.on_ground
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

    def _from_climb(self, state, timestamp):
        """Climb: level off → CRUISE; or descend directly → DESCENT."""
        if self._transition_if_held(
            "climb_to_descent",
            not state.on_ground and state.vertical_speed_fpm < self.DESCENT_VS_FPM,
            Phase.DESCENT,
            self.DESCENT_ENTRY_SECONDS,
            timestamp,
        ):
            return
        self._transition_if_held(
            "level_off",
            not state.on_ground and abs(state.vertical_speed_fpm) < self.LEVEL_OFF_VS_FPM,
            Phase.CRUISE,
            self.LEVEL_OFF_SECONDS,
            timestamp,
        )

    def _from_cruise(self, state, timestamp):
        """Cruise: sustained descent → DESCENT."""
        self._transition_if_held(
            "cruise_to_descent",
            not state.on_ground and state.vertical_speed_fpm < self.DESCENT_VS_FPM,
            Phase.DESCENT,
            self.DESCENT_ENTRY_SECONDS,
            timestamp,
        )

    def _from_descent(self, state, timestamp):
        """Descent: below approach altitude → APPROACH."""
        self._transition_if_held(
            "descent_to_approach",
            not state.on_ground and state.altitude_agl_ft < self.APPROACH_AGL_FT,
            Phase.APPROACH,
            self.APPROACH_ENTRY_SECONDS,
            timestamp,
        )

    def _from_approach(self, state, timestamp):
        """Approach: below final altitude → FINAL."""
        self._transition_if_held(
            "approach_to_final",
            not state.on_ground and state.altitude_agl_ft < self.FINAL_AGL_FT,
            Phase.FINAL,
            self.FINAL_ENTRY_SECONDS,
            timestamp,
        )

    def _from_final(self, state, timestamp):
        """Final: on ground → LANDING (touchdown)."""
        self._transition_if_held(
            "touchdown",
            state.on_ground,
            Phase.LANDING,
            self.TOUCHDOWN_SECONDS,
            timestamp,
        )

    def _from_landing(self, state, timestamp):
        """Landing roll: IAS drops below rotation speed → ROLLOUT."""
        self._transition_if_held(
            "landing_to_rollout",
            state.on_ground and state.indicated_airspeed_kt < self.ROLLOUT_IAS_KT,
            Phase.ROLLOUT,
            self.ROLLOUT_ENTRY_SECONDS,
            timestamp,
        )

    def _from_rollout(self, state, timestamp):
        """Rollout: ground speed drops to taxi speed → TAXI_IN."""
        self._transition_if_held(
            "rollout_to_taxi_in",
            state.on_ground and state.ground_speed_kt < self.TAXI_SPEED_KT,
            Phase.TAXI_IN,
            self.TAXI_IN_ENTRY_SECONDS,
            timestamp,
        )

    def _from_taxi_in(self, state, timestamp):
        """Taxi in: essentially stopped → PARKING."""
        self._transition_if_held(
            "taxi_in_to_parking",
            state.on_ground and state.ground_speed_kt < self.PARKING_SPEED_KT,
            Phase.PARKING,
            self.PARKING_ENTRY_SECONDS,
            timestamp,
        )

    def _from_parking(self, state, timestamp):
        """Parking: engine stops → SHUTDOWN."""
        self._transition_if_held(
            "parking_to_shutdown",
            not state.engine_running,
            Phase.SHUTDOWN,
            self.SHUTDOWN_SECONDS,
            timestamp,
        )

    # ------------------------------------------------------------------
    # Initial phase snap
    # ------------------------------------------------------------------

    def _snap_to_initial_phase(self, state):
        """
        Set the opening phase from actual aircraft state on the very first frame.

        Prevents the detector from being stuck at COLD_AND_DARK when the user
        loads into a flight that is already airborne or taxiing.  Ground-based
        engine states use normal hysteresis (COLD_AND_DARK → PRE_TAXI).

        on_runway is deliberately not used here: the ON_ANY_RUNWAY SimVar is
        unreliable in the Python-SimConnect library.
        """
        if not state.on_ground:
            if state.altitude_agl_ft > 3000:
                self.phase = Phase.CRUISE
            elif state.altitude_agl_ft > self.CRUISE_AGL_FT:
                self.phase = Phase.CLIMB
            elif state.altitude_agl_ft > self.FINAL_AGL_FT:
                self.phase = Phase.INITIAL_CLIMB
            else:
                self.phase = Phase.FINAL
        elif state.ground_speed_kt > self.TAXI_SPEED_KT:
            self.phase = Phase.TAXI_OUT
        # stationary on ground: leave COLD_AND_DARK, normal hysteresis applies

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
