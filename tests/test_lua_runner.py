"""
Tests for the LuaRunner and Lua rule evaluation pipeline.

Each test group targets one concern: state exposure, scoring API,
global rules, and C172-specific rules.
"""

from pathlib import Path

import pytest
from flight_instructor.aircraft_state import AircraftState
from flight_instructor.event_type import EventType
from flight_instructor.phase import Phase
from flight_instructor.score_card import ScoreCard
from flight_instructor.lua_runner import LuaRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_runner(lua_src):
    """Return a LuaRunner with inline Lua source (no file I/O)."""
    runner = LuaRunner()
    runner.load_string(lua_src)
    return runner


def evaluate(lua_src, state=None, phase=Phase.CRUISE, events=None):
    """Run inline Lua against a fresh ScoreCard and return it."""
    if state is None:
        state = AircraftState()
    if events is None:
        events = []
    card = ScoreCard()
    runner = make_runner(lua_src)
    runner.evaluate(state, phase, events, card, timestamp=0.0)
    return card


# ---------------------------------------------------------------------------
# 1. LuaRunner basics
# ---------------------------------------------------------------------------

class TestLuaRunnerBasics:
    def test_empty_script_leaves_score_intact(self):
        card = evaluate("")
        assert card.score() == 100

    def test_register_without_calling_evaluate_is_harmless(self):
        runner = LuaRunner()
        runner.load_string("register(function() end)")
        # no evaluate call — should not raise

    def test_multiple_load_string_calls_accumulate_rules(self):
        runner = LuaRunner()
        runner.load_string("register(function() safety.malus(5, 'a') end)")
        runner.load_string("register(function() safety.malus(3, 'b') end)")
        card = ScoreCard()
        runner.evaluate(AircraftState(), Phase.CRUISE, [], card, timestamp=0.0)
        assert card.score() == 92  # 100 - 5 - 3


# ---------------------------------------------------------------------------
# 2. State exposure — values land in Lua globals
# ---------------------------------------------------------------------------

class TestStateExposure:
    def _malus_if(self, condition_lua):
        """Lua snippet: apply malus 1 when condition is true."""
        return f"register(function() if {condition_lua} then safety.malus(1, 'test') end end)"

    def test_stall_warning_true(self):
        state = AircraftState(stall_warning=True)
        card = evaluate(self._malus_if("stall_warning"), state=state)
        assert card.score() == 99

    def test_stall_warning_false(self):
        state = AircraftState(stall_warning=False)
        card = evaluate(self._malus_if("stall_warning"), state=state)
        assert card.score() == 100

    def test_engine_running(self):
        state = AircraftState(engine_running=True)
        card = evaluate(self._malus_if("engine.running"), state=state)
        assert card.score() == 99

    def test_engine_rpm(self):
        state = AircraftState(engine_rpm=2300.0)
        card = evaluate(self._malus_if("engine.rpm > 2000"), state=state)
        assert card.score() == 99

    def test_position_on_ground(self):
        state = AircraftState(on_ground=True)
        card = evaluate(self._malus_if("position.on_ground"), state=state)
        assert card.score() == 99

    def test_position_ground_speed(self):
        state = AircraftState(ground_speed_kt=25.0)
        card = evaluate(self._malus_if("position.ground_speed > 20"), state=state)
        assert card.score() == 99

    def test_position_altitude_ft(self):
        state = AircraftState(altitude_ft=5000.0)
        card = evaluate(self._malus_if("position.altitude_ft > 4000"), state=state)
        assert card.score() == 99

    def test_position_altitude_agl_ft(self):
        state = AircraftState(altitude_agl_ft=1500.0)
        card = evaluate(self._malus_if("position.altitude_agl_ft > 1000"), state=state)
        assert card.score() == 99

    def test_position_ias(self):
        state = AircraftState(indicated_airspeed_kt=110.0)
        card = evaluate(self._malus_if("position.ias > 100"), state=state)
        assert card.score() == 99

    def test_position_vertical_speed_fpm(self):
        state = AircraftState(vertical_speed_fpm=-800.0)
        card = evaluate(self._malus_if("position.vertical_speed_fpm < -500"), state=state)
        assert card.score() == 99

    def test_lights_beacon(self):
        state = AircraftState(beacon_on=True)
        card = evaluate(self._malus_if("lights.beacon"), state=state)
        assert card.score() == 99

    def test_lights_taxi(self):
        state = AircraftState(taxi_light_on=True)
        card = evaluate(self._malus_if("lights.taxi"), state=state)
        assert card.score() == 99

    def test_lights_landing(self):
        state = AircraftState(landing_light_on=True)
        card = evaluate(self._malus_if("lights.landing"), state=state)
        assert card.score() == 99

    def test_lights_nav(self):
        state = AircraftState(nav_lights_on=True)
        card = evaluate(self._malus_if("lights.nav"), state=state)
        assert card.score() == 99

    def test_lights_strobe(self):
        state = AircraftState(strobe_on=True)
        card = evaluate(self._malus_if("lights.strobe"), state=state)
        assert card.score() == 99

    def test_controls_throttle(self):
        state = AircraftState(throttle_pct=80.0)
        card = evaluate(self._malus_if("controls.throttle_pct > 70"), state=state)
        assert card.score() == 99

    def test_controls_mixture(self):
        state = AircraftState(mixture_pct=50.0)
        card = evaluate(self._malus_if("controls.mixture_pct < 80"), state=state)
        assert card.score() == 99

    def test_controls_flaps(self):
        state = AircraftState(flaps_deg=10.0)
        card = evaluate(self._malus_if("controls.flaps_deg > 0"), state=state)
        assert card.score() == 99

    def test_controls_fuel_selector_both(self):
        state = AircraftState(fuel_selector_both=True)
        card = evaluate(self._malus_if("controls.fuel_selector_both"), state=state)
        assert card.score() == 99

    def test_controls_carb_heat(self):
        state = AircraftState(carb_heat_on=True)
        card = evaluate(self._malus_if("controls.carb_heat"), state=state)
        assert card.score() == 99

    def test_controls_parking_brake(self):
        state = AircraftState(parking_brake=True)
        card = evaluate(self._malus_if("controls.parking_brake"), state=state)
        assert card.score() == 99

    def test_attitude_bank_deg(self):
        state = AircraftState(bank_deg=35.0)
        card = evaluate(self._malus_if("attitude.bank_deg > 30"), state=state)
        assert card.score() == 99

    def test_attitude_pitch_deg(self):
        state = AircraftState(pitch_deg=-5.0)
        card = evaluate(self._malus_if("attitude.pitch_deg < 0"), state=state)
        assert card.score() == 99

    def test_phase_string(self):
        card = evaluate(
            self._malus_if('phase == "cruise"'),
            phase=Phase.CRUISE,
        )
        assert card.score() == 99

    def test_phase_other_value(self):
        card = evaluate(
            self._malus_if('phase == "cruise"'),
            phase=Phase.TAXI_OUT,
        )
        assert card.score() == 100


# ---------------------------------------------------------------------------
# 3. has_event() API
# ---------------------------------------------------------------------------

class TestHasEvent:
    def test_has_event_true_when_present(self):
        card = evaluate(
            "register(function() if has_event('takeoff_roll_started') then safety.malus(1, 'x') end end)",
            events=[EventType.TAKEOFF_ROLL_STARTED],
        )
        assert card.score() == 99

    def test_has_event_false_when_absent(self):
        card = evaluate(
            "register(function() if has_event('takeoff_roll_started') then safety.malus(1, 'x') end end)",
            events=[],
        )
        assert card.score() == 100

    def test_has_event_case_insensitive(self):
        card = evaluate(
            "register(function() if has_event('TAKEOFF_ROLL_STARTED') then safety.malus(1, 'x') end end)",
            events=[EventType.TAKEOFF_ROLL_STARTED],
        )
        assert card.score() == 99


# ---------------------------------------------------------------------------
# 4. Scoring API — all five categories
# ---------------------------------------------------------------------------

class TestScoringApi:
    def test_procedures_malus(self):
        from flight_instructor.score_category import ScoreCategory
        card = evaluate("register(function() procedures.malus(7, 'test') end)")
        assert card.category_score(ScoreCategory.PROCEDURES) == 93

    def test_safety_malus(self):
        from flight_instructor.score_category import ScoreCategory
        card = evaluate("register(function() safety.malus(10, 'test') end)")
        assert card.category_score(ScoreCategory.SAFETY) == 90

    def test_aircraft_handling_malus(self):
        from flight_instructor.score_category import ScoreCategory
        card = evaluate("register(function() aircraft_handling.malus(5, 'test') end)")
        assert card.category_score(ScoreCategory.AIRCRAFT_HANDLING) == 95

    def test_aircraft_care_malus(self):
        from flight_instructor.score_category import ScoreCategory
        card = evaluate("register(function() aircraft_care.malus(4, 'test') end)")
        assert card.category_score(ScoreCategory.AIRCRAFT_CARE) == 96

    def test_navigation_malus(self):
        from flight_instructor.score_category import ScoreCategory
        card = evaluate("register(function() navigation.malus(3, 'test') end)")
        assert card.category_score(ScoreCategory.NAVIGATION) == 97

    def test_score_cap(self):
        card = evaluate("register(function() score.cap(70, 'dangerous') end)")
        assert card.score() == 70

    def test_malus_appears_in_violations(self):
        card = evaluate("register(function() safety.malus(5, 'stall') end)")
        assert len(card.violations()) == 1
        assert card.violations()[0].description == "stall"

    def test_malus_deducts_from_total_score(self):
        card = evaluate("register(function() safety.malus(20, 'x') end)")
        assert card.score() == 80


# ---------------------------------------------------------------------------
# 5. Rising-edge — Lua closure locals keep state across frames
# ---------------------------------------------------------------------------

class TestRisingEdge:
    STALL_RULE = """
        local _active = false
        register(function()
            if stall_warning and not _active then
                _active = true
                safety.malus(15, "Stall warning active.")
            elseif not stall_warning then
                _active = false
            end
        end)
    """

    def test_stall_fires_once_per_episode(self):
        runner = make_runner(self.STALL_RULE)
        card = ScoreCard()
        state_on = AircraftState(stall_warning=True)
        state_off = AircraftState(stall_warning=False)

        runner.evaluate(state_on, Phase.FINAL, [], card, timestamp=0.0)
        runner.evaluate(state_on, Phase.FINAL, [], card, timestamp=0.2)
        runner.evaluate(state_off, Phase.FINAL, [], card, timestamp=0.4)
        runner.evaluate(state_on, Phase.FINAL, [], card, timestamp=0.6)

        # First episode: 1 fire. Second episode: 1 fire. Total malus = 30.
        assert card.score() == 70

    def test_stall_does_not_fire_when_warning_absent(self):
        runner = make_runner(self.STALL_RULE)
        card = ScoreCard()
        state_off = AircraftState(stall_warning=False)

        for i in range(5):
            runner.evaluate(state_off, Phase.CRUISE, [], card, timestamp=float(i))

        assert card.score() == 100


# ---------------------------------------------------------------------------
# 6. Global rules file
# ---------------------------------------------------------------------------

_RULES_DIR = Path(__file__).resolve().parent.parent / "src" / "flight_instructor" / "rules"


class TestGlobalRules:
    RULES_PATH = _RULES_DIR / "global.lua"

    def _runner(self):
        runner = LuaRunner()
        runner.load_file(self.RULES_PATH)
        return runner

    def _eval(self, state, phase=Phase.CRUISE, events=None):
        card = ScoreCard()
        runner = self._runner()
        runner.evaluate(state, phase, events or [], card, timestamp=0.0)
        return card

    # Stall warning
    def test_stall_warning_deducts_safety(self):
        from flight_instructor.score_category import ScoreCategory
        card = self._eval(AircraftState(stall_warning=True))
        assert card.category_score(ScoreCategory.SAFETY) < 100

    def test_no_stall_no_deduction(self):
        card = self._eval(AircraftState(stall_warning=False))
        assert card.score() == 100

    # Excessive bank
    def test_excessive_bank_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = AircraftState(bank_deg=60.0, on_ground=False)
        card = self._eval(state, phase=Phase.CRUISE)
        assert card.category_score(ScoreCategory.AIRCRAFT_HANDLING) < 100

    def test_normal_bank_no_deduction(self):
        state = AircraftState(bank_deg=20.0, on_ground=False)
        card = self._eval(state, phase=Phase.CRUISE)
        assert card.score() == 100

    def test_bank_on_ground_no_deduction(self):
        state = AircraftState(bank_deg=60.0, on_ground=True)
        card = self._eval(state, phase=Phase.TAXI_OUT)
        assert card.score() == 100

    # Excessive sink rate
    def test_excessive_sink_rate_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = AircraftState(vertical_speed_fpm=-1100.0, on_ground=False)
        card = self._eval(state, phase=Phase.APPROACH)
        assert card.category_score(ScoreCategory.AIRCRAFT_HANDLING) < 100

    def test_normal_sink_rate_no_deduction(self):
        state = AircraftState(vertical_speed_fpm=-400.0, on_ground=False)
        card = self._eval(state, phase=Phase.APPROACH)
        assert card.score() == 100

    def test_sink_on_ground_no_deduction(self):
        state = AircraftState(vertical_speed_fpm=-1500.0, on_ground=True)
        card = self._eval(state, phase=Phase.LANDING)
        assert card.score() == 100

    # Taxi speed
    def test_taxi_speed_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = AircraftState(ground_speed_kt=25.0, on_ground=True)
        card = self._eval(state, phase=Phase.TAXI_OUT)
        assert card.category_score(ScoreCategory.AIRCRAFT_CARE) < 100

    def test_normal_taxi_speed_no_deduction(self):
        state = AircraftState(ground_speed_kt=10.0, on_ground=True)
        card = self._eval(state, phase=Phase.TAXI_OUT)
        assert card.score() == 100

    def test_high_speed_not_in_taxi_no_deduction(self):
        state = AircraftState(ground_speed_kt=80.0, on_ground=False)
        card = self._eval(state, phase=Phase.CRUISE)
        assert card.score() == 100

    # Rising-edge: stall fires once per episode
    def test_stall_fires_once_per_continuous_episode(self):
        runner = self._runner()
        card = ScoreCard()

        for _ in range(3):
            runner.evaluate(AircraftState(stall_warning=True), Phase.FINAL, [], card, 0.0)
        initial = card.score()

        runner.evaluate(AircraftState(stall_warning=False), Phase.FINAL, [], card, 0.6)
        runner.evaluate(AircraftState(stall_warning=True), Phase.FINAL, [], card, 0.8)

        assert card.score() < initial  # second episode fired


# ---------------------------------------------------------------------------
# 7. C172 rules file
# ---------------------------------------------------------------------------

def _good_takeoff_state(**overrides):
    """
    Return an AircraftState that satisfies all C172 takeoff checks.

    Individual tests override exactly the field they're exercising.
    """
    defaults = dict(
        carb_heat_on=False,
        mixture_pct=100.0,
        altitude_ft=500.0,
        fuel_selector_both=True,
        landing_light_on=True,
        beacon_on=True,
    )
    defaults.update(overrides)
    return AircraftState(**defaults)


class TestC172Rules:
    RULES_PATH = _RULES_DIR / "c172.lua"

    def _runner(self):
        runner = LuaRunner()
        runner.load_file(self.RULES_PATH)
        return runner

    def _eval(self, state, phase=Phase.CRUISE, events=None):
        card = ScoreCard()
        runner = self._runner()
        runner.evaluate(state, phase, events or [], card, timestamp=0.0)
        return card

    # Carb heat at takeoff
    def test_carb_heat_at_takeoff_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = _good_takeoff_state(carb_heat_on=True)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.category_score(ScoreCategory.SAFETY) < 100

    def test_carb_heat_off_at_takeoff_ok(self):
        state = _good_takeoff_state(carb_heat_on=False)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.score() == 100

    def test_carb_heat_on_but_no_takeoff_event_ok(self):
        state = _good_takeoff_state(carb_heat_on=True)
        card = self._eval(state, events=[])
        assert card.score() == 100

    # Mixture at low-altitude takeoff
    def test_lean_mixture_low_altitude_takeoff_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = _good_takeoff_state(mixture_pct=50.0, altitude_ft=500.0)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.category_score(ScoreCategory.SAFETY) < 100

    def test_rich_mixture_low_altitude_takeoff_ok(self):
        state = _good_takeoff_state(mixture_pct=100.0, altitude_ft=500.0)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.score() == 100

    def test_lean_mixture_high_altitude_takeoff_ok(self):
        state = _good_takeoff_state(mixture_pct=50.0, altitude_ft=4000.0)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.score() == 100

    # Fuel selector at takeoff
    def test_fuel_not_both_at_takeoff_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = _good_takeoff_state(fuel_selector_both=False)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.category_score(ScoreCategory.SAFETY) < 100

    def test_fuel_both_at_takeoff_ok(self):
        state = _good_takeoff_state(fuel_selector_both=True)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.score() == 100

    # Landing light at takeoff
    def test_landing_light_off_at_takeoff_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = _good_takeoff_state(landing_light_on=False)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.category_score(ScoreCategory.PROCEDURES) < 100

    def test_landing_light_on_at_takeoff_ok(self):
        state = _good_takeoff_state(landing_light_on=True)
        card = self._eval(state, events=[EventType.TAKEOFF_ROLL_STARTED])
        assert card.score() == 100

    # Taxi light during taxi
    def test_taxi_light_off_during_taxi_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = AircraftState(taxi_light_on=False)
        card = self._eval(state, phase=Phase.TAXI_OUT)
        assert card.category_score(ScoreCategory.PROCEDURES) < 100

    def test_taxi_light_on_during_taxi_ok(self):
        state = AircraftState(taxi_light_on=True)
        card = self._eval(state, phase=Phase.TAXI_OUT)
        assert card.score() == 100

    def test_taxi_light_off_not_taxiing_ok(self):
        state = AircraftState(taxi_light_on=False)
        card = self._eval(state, phase=Phase.CRUISE)
        assert card.score() == 100

    # Beacon before engine
    def test_engine_started_without_beacon_deducts(self):
        from flight_instructor.score_category import ScoreCategory
        state = AircraftState(beacon_on=False)
        card = self._eval(state, events=[EventType.ENGINE_STARTED])
        assert card.category_score(ScoreCategory.PROCEDURES) < 100

    def test_engine_started_with_beacon_ok(self):
        state = AircraftState(beacon_on=True)
        card = self._eval(state, events=[EventType.ENGINE_STARTED])
        assert card.score() == 100

    def test_beacon_off_no_engine_start_ok(self):
        state = AircraftState(beacon_on=False)
        card = self._eval(state, events=[])
        assert card.score() == 100

    # Taxi light rising-edge: fires once when it goes off
    def test_taxi_light_rule_fires_once_per_episode(self):
        runner = self._runner()
        card = ScoreCard()

        # Light on → no violation
        runner.evaluate(AircraftState(taxi_light_on=True), Phase.TAXI_OUT, [], card, 0.0)
        assert card.score() == 100

        # Light off first frame → one violation
        runner.evaluate(AircraftState(taxi_light_on=False), Phase.TAXI_OUT, [], card, 0.2)
        score_after_first = card.score()
        assert score_after_first < 100

        # Light still off → no second violation
        runner.evaluate(AircraftState(taxi_light_on=False), Phase.TAXI_OUT, [], card, 0.4)
        assert card.score() == score_after_first

        # Light comes back on, then off again → new episode, new violation
        runner.evaluate(AircraftState(taxi_light_on=True), Phase.TAXI_OUT, [], card, 0.6)
        runner.evaluate(AircraftState(taxi_light_on=False), Phase.TAXI_OUT, [], card, 0.8)
        assert card.score() < score_after_first
