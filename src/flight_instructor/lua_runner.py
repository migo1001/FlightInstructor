import lupa
from flight_instructor.lua_category import LuaCategory
from flight_instructor.lua_score_api import LuaScoreApi
from flight_instructor.score_category import ScoreCategory


class LuaRunner:
    """
    Manages a persistent Lua runtime that hosts all flight rules.

    Rules are loaded once via load_file() or load_string() and stay resident
    across many evaluate() calls.  Each rule registers a closure with
    register(); those closures maintain their own local state (rising-edge
    flags etc.) across frames.

    The Python API exposed to Lua:
        procedures.malus(n, desc)   — record a Procedures violation
        safety.malus(n, desc)       — record a Safety violation
        aircraft_handling.malus(…)  — record an AircraftHandling violation
        aircraft_care.malus(…)      — record an AircraftCare violation
        navigation.malus(…)         — record a Navigation violation
        score.cap(max_score, reason)
        has_event(type_str)         — true if that EventType fired this frame
        phase                       — string, e.g. "takeoff_roll"
        stall_warning               — boolean
        engine.*                    — engine fields
        lights.*                    — light fields
        position.*                  — position/motion fields
        controls.*                  — control fields
        attitude.*                  — attitude fields
    """

    def __init__(self):
        """Create the Lua runtime and wire up the scoring API."""
        self._lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        self._rules = []
        self._current_events = set()

        self._categories = {
            ScoreCategory.PROCEDURES: LuaCategory(ScoreCategory.PROCEDURES, None),
            ScoreCategory.SAFETY: LuaCategory(ScoreCategory.SAFETY, None),
            ScoreCategory.AIRCRAFT_HANDLING: LuaCategory(ScoreCategory.AIRCRAFT_HANDLING, None),
            ScoreCategory.AIRCRAFT_CARE: LuaCategory(ScoreCategory.AIRCRAFT_CARE, None),
            ScoreCategory.NAVIGATION: LuaCategory(ScoreCategory.NAVIGATION, None),
        }
        self._score_api = LuaScoreApi(None)

        self._install_harness()

    def _install_harness(self):
        """Inject the register() function and all API objects into Lua globals."""
        rules_list = self._rules

        def register(fn):
            """Called by Lua rule files to add a rule closure."""
            rules_list.append(fn)

        g = self._lua.globals()
        g.register = register
        g.procedures = self._categories[ScoreCategory.PROCEDURES]
        g.safety = self._categories[ScoreCategory.SAFETY]
        g.aircraft_handling = self._categories[ScoreCategory.AIRCRAFT_HANDLING]
        g.aircraft_care = self._categories[ScoreCategory.AIRCRAFT_CARE]
        g.navigation = self._categories[ScoreCategory.NAVIGATION]
        g.score = self._score_api

        current_events = self._current_events

        def has_event(type_str):
            """Return true if the given EventType name fired this frame."""
            return type_str.upper() in current_events

        g.has_event = has_event

    def load_file(self, path):
        """Execute a Lua rule file, collecting all register() calls."""
        with open(path, "r") as f:
            source = f.read()
        self._lua.execute(source)

    def load_string(self, source):
        """Execute an inline Lua string, collecting all register() calls."""
        self._lua.execute(source)

    def evaluate(self, state, phase, events, score_card, timestamp):
        """
        Run all registered rules against one telemetry frame.

        state      — AircraftState
        phase      — Phase enum value
        events     — list of EventType values that fired this frame
        score_card — ScoreCard to write violations and caps into
        timestamp  — float seconds since session start
        """
        self._inject_state(state, phase)
        self._update_events(events)
        self._update_scoring_objects(score_card, timestamp)
        self._run_rules()

    def _inject_state(self, state, phase):
        """Push all AircraftState fields and phase into Lua globals."""
        g = self._lua.globals()

        g.phase = phase.value.lower()
        g.stall_warning = state.stall_warning

        g.engine = self._lua.table(
            running=state.engine_running,
            rpm=state.engine_rpm,
            oil_pressure_psi=state.oil_pressure_psi,
            oil_temp_c=state.oil_temp_c,
        )

        g.lights = self._lua.table(
            beacon=state.beacon_on,
            taxi=state.taxi_light_on,
            landing=state.landing_light_on,
            nav=state.nav_lights_on,
            strobe=state.strobe_on,
        )

        g.position = self._lua.table(
            on_ground=state.on_ground,
            on_runway=state.on_runway,
            ground_speed=state.ground_speed_kt,
            ias=state.indicated_airspeed_kt,
            altitude_ft=state.altitude_ft,
            altitude_agl_ft=state.altitude_agl_ft,
            vertical_speed_fpm=state.vertical_speed_fpm,
        )

        g.controls = self._lua.table(
            throttle_pct=state.throttle_pct,
            mixture_pct=state.mixture_pct,
            flaps_deg=state.flaps_deg,
            fuel_selector_both=state.fuel_selector_both,
            carb_heat=state.carb_heat_on,
            parking_brake=state.parking_brake,
        )

        g.attitude = self._lua.table(
            bank_deg=state.bank_deg,
            pitch_deg=state.pitch_deg,
            heading_deg=state.heading_deg,
        )

    def _update_events(self, events):
        """Replace the current event set with the events fired this frame."""
        self._current_events.clear()
        for event_type in events:
            self._current_events.add(event_type.name.upper())

    def _update_scoring_objects(self, score_card, timestamp):
        """Point all scoring objects at the current ScoreCard and timestamp."""
        for cat in self._categories.values():
            cat.set_score_card(score_card)
            cat.set_timestamp(timestamp)
        self._score_api.set_score_card(score_card)
        self._score_api.set_timestamp(timestamp)

    def _run_rules(self):
        """Call every registered rule closure, logging errors without stopping evaluation."""
        import logging
        for rule_fn in self._rules:
            try:
                rule_fn()
            except Exception as exc:
                logging.warning("Rule error: %s", exc)
