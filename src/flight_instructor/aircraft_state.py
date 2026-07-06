class AircraftState:
    """
    Normalized snapshot of aircraft state from a single telemetry poll.

    All values are in standard aviation units: knots, feet, RPM, degrees,
    percent (0-100). Defaults represent a cold-and-dark aircraft at the ramp.
    """

    def __init__(self, **kwargs):
        # Position and surface
        self.latitude = kwargs.get("latitude", 0.0)
        self.longitude = kwargs.get("longitude", 0.0)
        self.altitude_ft = kwargs.get("altitude_ft", 0.0)
        self.altitude_agl_ft = kwargs.get("altitude_agl_ft", 0.0)
        self.on_ground = kwargs.get("on_ground", True)
        self.on_runway = kwargs.get("on_runway", False)

        # Motion
        self.ground_speed_kt = kwargs.get("ground_speed_kt", 0.0)
        self.indicated_airspeed_kt = kwargs.get("indicated_airspeed_kt", 0.0)
        self.vertical_speed_fpm = kwargs.get("vertical_speed_fpm", 0.0)
        self.pitch_deg = kwargs.get("pitch_deg", 0.0)
        self.bank_deg = kwargs.get("bank_deg", 0.0)
        self.heading_deg = kwargs.get("heading_deg", 0.0)

        # Engine
        self.engine_running = kwargs.get("engine_running", False)
        self.engine_rpm = kwargs.get("engine_rpm", 0.0)
        self.oil_pressure_psi = kwargs.get("oil_pressure_psi", 0.0)
        self.oil_temp_c = kwargs.get("oil_temp_c", 15.0)

        # Controls
        self.throttle_pct = kwargs.get("throttle_pct", 0.0)
        self.mixture_pct = kwargs.get("mixture_pct", 100.0)
        self.flaps_deg = kwargs.get("flaps_deg", 0.0)
        self.elevator_trim_pct = kwargs.get("elevator_trim_pct", 0.0)
        self.parking_brake = kwargs.get("parking_brake", True)
        self.fuel_selector_both = kwargs.get("fuel_selector_both", True)

        # Lights
        self.beacon_on = kwargs.get("beacon_on", False)
        self.taxi_light_on = kwargs.get("taxi_light_on", False)
        self.landing_light_on = kwargs.get("landing_light_on", False)
        self.nav_lights_on = kwargs.get("nav_lights_on", False)
        self.strobe_on = kwargs.get("strobe_on", False)

        # Environment
        self.pitot_heat_on = kwargs.get("pitot_heat_on", False)
        self.carb_heat_on = kwargs.get("carb_heat_on", False)
        self.outside_air_temp_c = kwargs.get("outside_air_temp_c", 15.0)

        # Warnings (pre-computed by the simulator)
        self.stall_warning = kwargs.get("stall_warning", False)
