import math
import time


class LocationService:
    """
    Resolves the aircraft's lat/lon to a human-readable position label.

    Uses the airportsdata package (bundled with the exe) to find the nearest
    airport by ICAO code, then combines that with runway and surface state to
    produce a label such as:
        "Rwy 27 at LFPG"
        "Taxiing at LFPO"
        "Ramp at LFPN"
        "Airborne · LFPG"
        "Airborne"

    Gate and taxiway letter identification requires SimConnect's Facilities API,
    which is not yet exposed by the Python SimConnect library.

    The nearest-airport search is O(n) with a bounding-box pre-filter and is
    cached; it runs at most once every UPDATE_INTERVAL_S seconds.
    """

    NEARBY_KM       = 50.0   # Report airport name if within this distance
    UPDATE_INTERVAL = 5.0    # Seconds between nearest-airport searches
    EARTH_R_KM      = 6371.0

    def __init__(self):
        """Load the airport database once at startup."""
        self._airports        = self._load_airports()
        self._cached_icao     = None
        self._cached_km       = None
        self._last_search     = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def describe(self, state):
        """
        Return a position string for the current aircraft state.

        Returns an empty string if no lat/lon data is available yet.
        """
        lat, lon = state.latitude, state.longitude
        if lat == 0.0 and lon == 0.0:
            return ""

        self._refresh_if_due(lat, lon)
        return self._format(state)

    # ------------------------------------------------------------------
    # Airport lookup
    # ------------------------------------------------------------------

    def _load_airports(self):
        """Load ICAO-keyed airport dict from the airportsdata package."""
        try:
            import airportsdata
            return airportsdata.load("ICAO")
        except Exception:
            return {}

    def _refresh_if_due(self, lat, lon):
        """Run nearest-airport search if the cache is stale."""
        now = time.monotonic()
        if self._last_search is None or now - self._last_search > self.UPDATE_INTERVAL:
            self._search_nearest(lat, lon)
            self._last_search = now

    def _search_nearest(self, lat, lon):
        """Find the nearest airport within NEARBY_KM and cache its ICAO."""
        lat_margin = self.NEARBY_KM / 111.0
        lon_margin = self.NEARBY_KM / max(111.0 * math.cos(math.radians(lat)), 1.0)

        best_icao = None
        best_km   = self.NEARBY_KM

        for icao, ap in self._airports.items():
            if abs(ap["lat"] - lat) > lat_margin:
                continue
            if abs(ap["lon"] - lon) > lon_margin:
                continue
            km = self._haversine(lat, lon, ap["lat"], ap["lon"])
            if km < best_km:
                best_km   = km
                best_icao = icao

        self._cached_icao = best_icao
        self._cached_km   = best_km if best_icao else None

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Return great-circle distance in km."""
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1))
             * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return self.EARTH_R_KM * 2 * math.asin(math.sqrt(a))

    # ------------------------------------------------------------------
    # Label formatting
    # ------------------------------------------------------------------

    def _format(self, state):
        """Build the position string from cached airport and current state."""
        at = f" at {self._cached_icao}" if self._cached_icao else ""

        if not state.on_ground:
            if self._cached_icao:
                return f"Airborne · {self._cached_icao}"
            return "Airborne"

        if state.on_runway:
            rwy = self._runway_from_heading(state.heading_deg)
            return f"Rwy {rwy}{at}"

        if state.ground_speed_kt < 1.0:
            return f"Ramp{at}"

        return f"Taxiing{at}"

    def _runway_from_heading(self, heading_deg):
        """
        Approximate runway designator from magnetic heading.

        Runway 27 has heading ~270°, runway 09 has heading ~090°, etc.
        L/R/C suffixes require a runway database and are omitted.
        """
        rwy_num = round(heading_deg / 10) % 36
        if rwy_num == 0:
            rwy_num = 36
        return f"{rwy_num:02d}"
