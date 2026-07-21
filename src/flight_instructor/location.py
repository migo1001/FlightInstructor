import math
import time


class LocationService:
    """
    Resolves the aircraft's lat/lon to a human-readable position label.

    When a FacilitiesClient is provided (and has received data for the current
    airport), the label is precise:
        "Gate F32 at LFPG"      — parked at a named gate
        "Ramp 7 at LFPG"        — parked at a numbered ramp
        "Rwy 27L at LFPG"       — on-runway with exact L/R/C suffix
        "Taxiing at LFPO"        — ground, moving, no facilities yet
        "Airborne · LFPG"        — airborne near an airport
        "Airborne"               — en route, no airport within range

    Without a FacilitiesClient (or while waiting for the async response),
    runway designator is estimated from heading and parked position shows "Ramp".

    The nearest-airport search is O(n) with a bounding-box pre-filter; it runs
    at most once every UPDATE_INTERVAL seconds and its result is cached.
    """

    NEARBY_KM              = 50.0
    UPDATE_INTERVAL_GROUND = 5.0    # seconds between searches while on the ground
    UPDATE_INTERVAL_AIR    = 30.0   # airborne: display-only, no need for precision
    EARTH_R_KM             = 6371.0

    def __init__(self, facilities=None):
        """
        facilities — optional FacilitiesClient; if provided, gate/runway names
                     are retrieved from SimConnect rather than estimated.
        """
        self._airports      = self._load_airports()
        self._facilities    = facilities
        self._cached_icao   = None
        self._last_search   = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def describe(self, state):
        """
        Return a position string for the current aircraft state.

        Returns an empty string when lat/lon is not yet available.
        """
        lat, lon = state.latitude, state.longitude
        if lat == 0.0 and lon == 0.0:
            return ""

        prev_icao = self._cached_icao
        self._refresh_if_due(lat, lon, state.on_ground)

        # Request facilities only when on the ground at a new airport.
        # Airborne: ICAO is for display only; we don't need parking/runway data.
        if (state.on_ground
                and self._cached_icao
                and self._cached_icao != prev_icao
                and self._facilities):
            self._facilities.request_airport(self._cached_icao)

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

    def _refresh_if_due(self, lat, lon, on_ground):
        """Run nearest-airport search if the cache is stale."""
        interval = self.UPDATE_INTERVAL_GROUND if on_ground else self.UPDATE_INTERVAL_AIR
        now = time.monotonic()
        if self._last_search is None or now - self._last_search > interval:
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
        """Build the position string from cached airport + facilities data."""
        icao = self._cached_icao
        at   = f" at {icao}" if icao else ""

        if not state.on_ground:
            return f"Airborne · {icao}" if icao else "Airborne"

        if state.on_runway:
            return f"Rwy {self._runway_label(state, icao)}{at}"

        if state.ground_speed_kt < 1.0:
            label = self._parking_label(state, icao)
            return f"{label}{at}"

        return f"Taxiing{at}"

    def _runway_label(self, state, icao):
        """
        Return a runway designator string.

        Uses SimConnect Facilities runway threshold positions when available
        (gives exact L/R/C suffix). Falls back to heading-derived estimate.
        """
        if self._facilities and icao and self._facilities.has_data(icao):
            rwy = self._facilities.nearest_runway(
                state.latitude, state.longitude, state.heading_deg, icao
            )
            if rwy:
                return rwy.designator

        return self._rwy_from_heading(state.heading_deg)

    def _parking_label(self, state, icao):
        """
        Return a parking label: 'Gate F32', 'Ramp 7', etc.

        Uses SimConnect Facilities gate/stand data when available.
        Falls back to 'Ramp' while data is loading or unavailable.
        """
        if self._facilities and icao:
            if not self._facilities.has_data(icao):
                # Data still loading — show "Ramp" until it arrives
                return "Ramp"
            spot = self._facilities.nearest_parking(state.latitude, state.longitude, icao)
            if spot:
                return spot.label

        return "Ramp"

    def _rwy_from_heading(self, heading_deg):
        """
        Estimate runway designator from magnetic heading.

        Runway 27 ≈ 270°, runway 09 ≈ 090°.  L/R/C requires threshold data.
        """
        rwy_num = round(heading_deg / 10) % 36
        if rwy_num == 0:
            rwy_num = 36
        return f"{rwy_num:02d}"
