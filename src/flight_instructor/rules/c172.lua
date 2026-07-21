-- Cessna 172 profile.
--
-- configure_phases() sets aircraft-specific thresholds in the Python phase
-- detector.  Every key here overrides the detector's class-level default.
-- Only keys listed in PhaseDetector._CONFIGURABLE are recognised.

configure_phases({
    runup_rpm           = 1800.0,   -- minimum RPM for a valid magneto check
    runup_exit_rpm      = 1000.0,   -- RPM below which run-up is considered done
    takeoff_throttle_pct = 70.0,    -- throttle level that marks start of roll
    rollout_ias_kt      = 60.0,     -- IAS below which landing roll transitions to rollout
    cruise_agl_ft       = 1000.0,   -- AGL at which climb becomes cruise
    final_agl_ft        = 500.0,    -- AGL at which approach becomes final
})

-- ── C172-specific scoring rules ──────────────────────────────────────────────

-- Carburettor heat must be off at takeoff roll start.
register(function()
    if not has_event("TAKEOFF_ROLL_STARTED") then return end
    if controls.carb_heat then
        safety.malus(8, "Takeoff roll started with carburettor heat on.")
    end
end)

-- Mixture must be full rich below 3000 ft at takeoff.
local HIGH_ALT_FT = 3000.0
local RICH_THRESHOLD_PCT = 90.0
register(function()
    if not has_event("TAKEOFF_ROLL_STARTED") then return end
    if position.altitude_ft < HIGH_ALT_FT and controls.mixture_pct < RICH_THRESHOLD_PCT then
        safety.malus(8, string.format(
            "Takeoff at low altitude with mixture at %.0f%%. Full rich required below %.0f ft.",
            controls.mixture_pct, HIGH_ALT_FT
        ))
    end
end)

-- Fuel selector must be on BOTH at takeoff roll start.
register(function()
    if not has_event("TAKEOFF_ROLL_STARTED") then return end
    if not controls.fuel_selector_both then
        safety.malus(10, "Takeoff roll started with fuel selector not set to BOTH.", "serious")
    end
end)

-- Landing light must be on at takeoff roll start.
register(function()
    if not has_event("TAKEOFF_ROLL_STARTED") then return end
    if not lights.landing then
        procedures.malus(5, "Takeoff roll started without landing light on.")
    end
end)

-- Taxi light must be on while taxiing (rising-edge: one penalty per episode).
local TAXI_PHASES = { taxi_out = true, taxi_in = true }
local _taxi_light_off_active = false
register(function()
    if not TAXI_PHASES[phase] then
        _taxi_light_off_active = false
        return
    end
    if not lights.taxi and not _taxi_light_off_active then
        _taxi_light_off_active = true
        procedures.malus(3, "Taxi light off while taxiing.", "minor")
    elseif lights.taxi then
        _taxi_light_off_active = false
    end
end)

-- Beacon must be on before engine start.
register(function()
    if not has_event("ENGINE_STARTED") then return end
    if not lights.beacon then
        procedures.malus(5, "Engine started without beacon on.")
    end
end)
