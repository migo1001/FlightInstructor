-- Global rules that apply to every aircraft type.
-- Each rule uses a closure-local flag for rising-edge detection so a single
-- continuous episode produces exactly one penalty.

-- Stall warning
local _stall_active = false
register(function()
    if warnings.stall and not _stall_active then
        _stall_active = true
        safety.malus(15, "Stall warning active.", "critical")
    elseif not warnings.stall then
        _stall_active = false
    end
end)

-- Excessive bank angle (airborne only)
local BANK_LIMIT = 45.0
local _bank_active = false
register(function()
    if position.on_ground then
        _bank_active = false
        return
    end
    local bank = attitude.bank_deg
    if bank < 0 then bank = -bank end
    if bank > BANK_LIMIT and not _bank_active then
        _bank_active = true
        aircraft_handling.malus(10, string.format("Excessive bank angle: %.0f deg (limit %d deg).", bank, BANK_LIMIT), "serious")
    elseif bank <= BANK_LIMIT then
        _bank_active = false
    end
end)

-- Excessive sink rate (airborne only)
local SINK_LIMIT_FPM = -1000.0
local _sink_active = false
register(function()
    if position.on_ground then
        _sink_active = false
        return
    end
    if position.vertical_speed_fpm < SINK_LIMIT_FPM and not _sink_active then
        _sink_active = true
        aircraft_handling.malus(10, string.format("Excessive sink rate: %.0f fpm (limit %d fpm).", position.vertical_speed_fpm, SINK_LIMIT_FPM), "serious")
    elseif position.vertical_speed_fpm >= SINK_LIMIT_FPM then
        _sink_active = false
    end
end)

-- VFR cloud entry (airborne only)
local _in_cloud_active = false
register(function()
    if position.on_ground then
        _in_cloud_active = false
        return
    end
    if weather.in_cloud and not _in_cloud_active then
        _in_cloud_active = true
        navigation.malus(10, "Flying in cloud under VFR.", "serious")
    elseif not weather.in_cloud then
        _in_cloud_active = false
    end
end)

-- Excessive taxi speed (taxi phases only)
local TAXI_SPEED_LIMIT_KT = 20.0
local TAXI_PHASES = { taxi_out = true, taxi_in = true }
local _taxi_speed_active = false
register(function()
    if not TAXI_PHASES[phase] then
        _taxi_speed_active = false
        return
    end
    if position.ground_speed > TAXI_SPEED_LIMIT_KT and not _taxi_speed_active then
        _taxi_speed_active = true
        aircraft_care.malus(5, string.format("Taxi speed excessive: %.0f kt (limit %d kt).", position.ground_speed, TAXI_SPEED_LIMIT_KT))
    elseif position.ground_speed <= TAXI_SPEED_LIMIT_KT then
        _taxi_speed_active = false
    end
end)
