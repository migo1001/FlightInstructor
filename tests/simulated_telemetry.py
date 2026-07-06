from flight_instructor.aircraft_state import AircraftState


class SimulatedTelemetry:
    """
    Generates realistic C172 AircraftState snapshots for testing.

    Maintains an internal clock so successive feed() calls produce
    monotonically increasing timestamps that match what SimConnect would deliver.
    Default sample rate is 5 Hz, matching a typical light-duty polling interval.
    """

    FPS = 5.0

    def __init__(self):
        """Initialize the clock at t=0."""
        self._current_time = 0.0

    def feed(self, detector, state, seconds):
        """Push a fixed state to the detector repeatedly for the given duration."""
        n_frames = int(seconds * self.FPS)
        for _ in range(n_frames):
            detector.update(state, self._current_time)
            self._current_time += 1.0 / self.FPS

    def cold_and_dark(self):
        """C172 parked at the ramp, everything off."""
        return AircraftState(
            on_ground=True,
            on_runway=False,
            engine_running=False,
            engine_rpm=0.0,
            ground_speed_kt=0.0,
            indicated_airspeed_kt=0.0,
            altitude_agl_ft=0.0,
            vertical_speed_fpm=0.0,
            throttle_pct=0.0,
            parking_brake=True,
            beacon_on=False,
            taxi_light_on=False,
            landing_light_on=False,
            nav_lights_on=False,
        )

    def engine_at_idle(self):
        """C172 engine running at ground idle (~750 RPM), parked."""
        return AircraftState(
            on_ground=True,
            on_runway=False,
            engine_running=True,
            engine_rpm=750.0,
            oil_pressure_psi=45.0,
            oil_temp_c=30.0,
            ground_speed_kt=0.0,
            indicated_airspeed_kt=0.0,
            altitude_agl_ft=0.0,
            vertical_speed_fpm=0.0,
            throttle_pct=5.0,
            parking_brake=True,
            beacon_on=True,
        )

    def taxiing(self, ground_speed_kt=10.0):
        """C172 taxiing at normal speed with parking brake released."""
        return AircraftState(
            on_ground=True,
            on_runway=False,
            engine_running=True,
            engine_rpm=1000.0,
            oil_pressure_psi=50.0,
            oil_temp_c=50.0,
            ground_speed_kt=ground_speed_kt,
            indicated_airspeed_kt=0.0,
            altitude_agl_ft=0.0,
            vertical_speed_fpm=0.0,
            throttle_pct=15.0,
            parking_brake=False,
            beacon_on=True,
            taxi_light_on=True,
        )

    def run_up(self):
        """C172 stationary at the run-up area, magneto-check power (~1800 RPM)."""
        return AircraftState(
            on_ground=True,
            on_runway=False,
            engine_running=True,
            engine_rpm=1800.0,
            oil_pressure_psi=55.0,
            oil_temp_c=65.0,
            ground_speed_kt=0.0,
            indicated_airspeed_kt=0.0,
            altitude_agl_ft=0.0,
            vertical_speed_fpm=0.0,
            throttle_pct=45.0,
            parking_brake=True,
            beacon_on=True,
            taxi_light_on=True,
        )

    def lined_up(self):
        """C172 lined up on the runway at idle, awaiting takeoff clearance."""
        return AircraftState(
            on_ground=True,
            on_runway=True,
            engine_running=True,
            engine_rpm=800.0,
            oil_pressure_psi=55.0,
            oil_temp_c=70.0,
            ground_speed_kt=0.0,
            indicated_airspeed_kt=0.0,
            altitude_agl_ft=0.0,
            vertical_speed_fpm=0.0,
            throttle_pct=5.0,
            parking_brake=False,
            beacon_on=True,
            landing_light_on=True,
            strobe_on=True,
        )

    def takeoff_roll(self, on_runway=True, ground_speed_kt=40.0):
        """C172 accelerating down the runway at full power."""
        return AircraftState(
            on_ground=True,
            on_runway=on_runway,
            engine_running=True,
            engine_rpm=2300.0,
            oil_pressure_psi=60.0,
            oil_temp_c=75.0,
            ground_speed_kt=ground_speed_kt,
            indicated_airspeed_kt=ground_speed_kt,
            altitude_agl_ft=0.0,
            vertical_speed_fpm=0.0,
            throttle_pct=100.0,
            parking_brake=False,
            beacon_on=True,
            landing_light_on=True,
            strobe_on=True,
        )

    def airborne(self, altitude_agl_ft=50.0, vertical_speed_fpm=600.0):
        """C172 just after rotation, wheels off the ground."""
        return AircraftState(
            on_ground=False,
            on_runway=False,
            engine_running=True,
            engine_rpm=2300.0,
            ground_speed_kt=65.0,
            indicated_airspeed_kt=65.0,
            altitude_agl_ft=altitude_agl_ft,
            vertical_speed_fpm=vertical_speed_fpm,
            pitch_deg=8.0,
            throttle_pct=100.0,
            parking_brake=False,
            beacon_on=True,
            landing_light_on=True,
            strobe_on=True,
        )

    def climbing(self, altitude_agl_ft=500.0, vertical_speed_fpm=700.0):
        """C172 in a steady climb, altitude established."""
        return AircraftState(
            on_ground=False,
            on_runway=False,
            engine_running=True,
            engine_rpm=2300.0,
            ground_speed_kt=75.0,
            indicated_airspeed_kt=75.0,
            altitude_agl_ft=altitude_agl_ft,
            vertical_speed_fpm=vertical_speed_fpm,
            pitch_deg=6.0,
            throttle_pct=100.0,
            parking_brake=False,
        )
