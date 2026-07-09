from flight_instructor.aircraft_state import AircraftState


class SimConnectSource:
    """
    Reads aircraft state from MSFS 2020 via SimConnect.

    Uses the Python-SimConnect library (pip install SimConnect).  All reads are
    non-blocking; if a variable is unavailable the field is left at its default.

    On any connection error the source drops to disconnected state and the
    caller can retry by calling connect() again.

    NOTE: on_runway is approximated as on_ground because MSFS does not expose
    a reliable per-user-aircraft "on runway" flag via SimConnect.  The phase
    detector may briefly enter LINEUP on slow-speed taxi; this is a known
    limitation to be improved with GPS + airport-database lookup.
    """

    POLL_INTERVAL_MS = 200  # 5 Hz

    # SimVar name → kwargs key for AircraftState (floats / raw numerics)
    _FLOAT_VARS = {
        "PLANE_ALTITUDE":                       "altitude_ft",
        "PLANE_ALT_ABOVE_GROUND":               "altitude_agl_ft",
        "GROUND_VELOCITY":                      "ground_speed_kt",
        "AIRSPEED_INDICATED":                   "indicated_airspeed_kt",
        "VERTICAL_SPEED":                       "vertical_speed_fpm",
        "PLANE_PITCH_DEGREES":                  "pitch_deg",
        "PLANE_BANK_DEGREES":                   "bank_deg",
        "PLANE_HEADING_DEGREES_MAGNETIC":       "heading_deg",
        "GENERAL_ENG_RPM:1":                    "engine_rpm",
        "GENERAL_ENG_OIL_PRESSURE:1":           "oil_pressure_psi",
        "GENERAL_ENG_THROTTLE_LEVER_POSITION:1":"throttle_pct",
        "MIXTURE_LEVER_POSITION:1":             "mixture_pct",
        "TRAILING_EDGE_FLAPS_LEFT_ANGLE":       "flaps_deg",
        "ELEVATOR_TRIM_PCT":                    "elevator_trim_pct",
        "AMBIENT_TEMPERATURE":                  "outside_air_temp_c",
    }

    # SimVar name → kwargs key for AircraftState (boolean: nonzero = True)
    _BOOL_VARS = {
        "SIM_ON_GROUND":              "on_ground",
        "GENERAL_ENG_COMBUSTION:1":   "engine_running",
        "BRAKE_PARKING_INDICATOR":    "parking_brake",
        "LIGHT_BEACON":               "beacon_on",
        "LIGHT_TAXI":                 "taxi_light_on",
        "LIGHT_LANDING":              "landing_light_on",
        "LIGHT_NAV":                  "nav_lights_on",
        "LIGHT_STROBE":               "strobe_on",
        "PITOT_HEAT":                 "pitot_heat_on",
        "STALL_WARNING":              "stall_warning",
    }

    def __init__(self):
        """Create a disconnected source."""
        self._sm = None
        self._aq = None
        self._connected = False

    def connect(self):
        """
        Attempt to connect to MSFS via SimConnect.

        Raises RuntimeError with a user-readable message distinguishing a
        missing Python package from MSFS not running.
        """
        try:
            from SimConnect import SimConnect, AircraftRequests
        except ImportError:
            raise RuntimeError(
                "SimConnect package not installed. "
                "Run: pip install SimConnect"
            )
        try:
            self._sm = SimConnect()
        except Exception as exc:
            raise RuntimeError(f"MSFS not running or SimConnect failed: {exc}") from exc
        self._aq = AircraftRequests(self._sm, _time=self.POLL_INTERVAL_MS)
        self._connected = True

    def disconnect(self):
        """Close the SimConnect connection."""
        self._connected = False
        if self._sm:
            try:
                self._sm.exit()
            except Exception:
                pass
        self._sm = None
        self._aq = None

    def is_connected(self):
        """Return True while a live SimConnect session is open."""
        return self._connected

    def read(self):
        """
        Poll one frame of aircraft state.

        Returns an AircraftState on success, or None if the connection has
        been lost.  On any read error the source disconnects itself so the
        caller can react.
        """
        if not self._connected:
            return None
        try:
            return self._build_state()
        except Exception:
            self.disconnect()
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_state(self):
        """Read all SimVars and assemble an AircraftState."""
        kwargs = {}

        for simvar, field in self._FLOAT_VARS.items():
            val = self._safe_get(simvar)
            if val is not None:
                kwargs[field] = float(val)

        for simvar, field in self._BOOL_VARS.items():
            val = self._safe_get(simvar)
            if val is not None:
                kwargs[field] = bool(val)

        self._read_oil_temp(kwargs)
        self._read_carb_heat(kwargs)
        self._read_fuel_selector(kwargs)

        # on_runway approximation — see class docstring
        kwargs["on_runway"] = kwargs.get("on_ground", True)

        return AircraftState(**kwargs)

    def _safe_get(self, simvar):
        """Return the SimVar value or None if unavailable."""
        try:
            return self._aq.get(simvar)
        except Exception:
            return None

    def _read_oil_temp(self, kwargs):
        """GENERAL_ENG_OIL_TEMPERATURE is in Rankine; convert to Celsius."""
        val = self._safe_get("GENERAL_ENG_OIL_TEMPERATURE:1")
        if val is not None and float(val) > 0:
            kwargs["oil_temp_c"] = (float(val) - 491.67) * 5.0 / 9.0

    def _read_carb_heat(self, kwargs):
        """CARB_HEAT_CONTROL is 0-100; treat > 50 as on."""
        val = self._safe_get("CARB_HEAT_CONTROL")
        if val is not None:
            kwargs["carb_heat_on"] = float(val) > 50.0

    def _read_fuel_selector(self, kwargs):
        """FUEL_TANK_SELECTOR enum: 0=off, 1=all/both, 2=left, 3=right."""
        val = self._safe_get("FUEL_TANK_SELECTOR:1")
        if val is not None:
            kwargs["fuel_selector_both"] = int(val) == 1
