"""
SimConnect Facilities client for MSFS 2020.

Uses SimConnect_AddToFacilityDefinition + SimConnect_RequestFacilityData to
retrieve per-airport data: runway threshold positions (enabling precise 27L/09R
designators) and parking spots (gate name, stand number, position).

Runs its own SimConnect connection in a background thread, separate from the
telemetry connection in SimConnectSource so failures here never affect scoring.
Results are cached per airport ICAO and shared via thread-safe structures.

Typical usage:
    client = FacilitiesClient()
    client.connect()                        # call once after MSFS is running
    client.request_airport("LFPG")          # async; results arrive in ~1 s
    spot  = client.nearest_parking(lat, lon, "LFPG")   # -> ParkingSpot or None
    rwy   = client.nearest_runway(lat, lon, hdg, "LFPG") # -> RunwayEnd or None
    client.disconnect()
"""

import ctypes
import logging
import math
import os
import threading

log = logging.getLogger(__name__)

# ── platform guard ────────────────────────────────────────────────────────────
# All SimConnect calls are Windows-only; on Linux this module loads but does
# nothing so tests and development still import cleanly.
_ON_WINDOWS = os.name == "nt"

# ── SimConnect message IDs (from SimConnect.h / MSFS 2020 SDK) ───────────────
_RECV_ID_OPEN          = 2
_RECV_ID_QUIT          = 3
_RECV_ID_FACILITY_DATA = 32   # MSFS 2020 addition
_RECV_ID_FACILITY_END  = 33   # MSFS 2020 addition — signals all data delivered

# Facility record types returned in SIMCONNECT_RECV_FACILITY_DATA.Type
_FAC_AIRPORT = 0
_FAC_RUNWAY  = 1
_FAC_PARKING = 2

# Arbitrary IDs we use for our definition and request
_DEF_AIRPORT = 1
_REQ_AIRPORT = 1

# Parking type codes (SIMCONNECT_PARKING_TYPE enum)
_PARK_RAMP_GA     = 1
_PARK_RAMP_CARGO  = 2
_PARK_RAMP_MIL_CARGO = 3
_PARK_RAMP_MIL_COMBAT = 4
_PARK_GATE        = 5
_PARK_DOCK        = 6

_PARK_LABELS = {
    _PARK_RAMP_GA:         "Ramp",
    _PARK_RAMP_CARGO:      "Cargo",
    _PARK_RAMP_MIL_CARGO:  "Mil Cargo",
    _PARK_RAMP_MIL_COMBAT: "Mil Combat",
    _PARK_GATE:            "Gate",
    _PARK_DOCK:            "Dock",
}

# ── ctypes structures (MSFS 2020 SimConnect binary layout) ───────────────────

class _RecvBase(ctypes.Structure):
    _fields_ = [
        ("dwSize",    ctypes.c_uint32),
        ("dwVersion", ctypes.c_uint32),
        ("dwID",      ctypes.c_uint32),
    ]

class _RecvFacilityData(ctypes.Structure):
    """Header for SIMCONNECT_RECV_FACILITY_DATA messages."""
    _fields_ = [
        ("dwSize",          ctypes.c_uint32),
        ("dwVersion",       ctypes.c_uint32),
        ("dwID",            ctypes.c_uint32),
        ("UserRequestId",   ctypes.c_uint32),
        ("UniqueRequestId", ctypes.c_uint32),
        ("Type",            ctypes.c_uint32),   # _FAC_* constant
        ("ItemIndex",       ctypes.c_uint32),
        ("ListSize",        ctypes.c_uint32),
        # Variable-length payload follows immediately in memory
    ]

# Binary layouts for each record type — must match the AddToFacilityDefinition
# field sequence exactly (name → type in SDK, Python ctypes type, size):
#
#   OPEN AIRPORT
#     LATITUDE   → FLOAT64 → c_double
#     LONGITUDE  → FLOAT64 → c_double
#   OPEN RUNWAY
#     IDENT            → STRING8  → c_char * 8
#     SECONDARY_IDENT  → STRING8  → c_char * 8
#     LATITUDE         → FLOAT64  → c_double
#     LONGITUDE        → FLOAT64  → c_double
#     SECONDARY_LATITUDE  → FLOAT64 → c_double
#     SECONDARY_LONGITUDE → FLOAT64 → c_double
#   CLOSE RUNWAY
#   OPEN PARKING
#     LATITUDE   → FLOAT64  → c_double
#     LONGITUDE  → FLOAT64  → c_double
#     HEADING    → FLOAT32  → c_float
#     NAME       → STRING8  → c_char * 8   (e.g. b"GATE_F")
#     NUMBER     → INT16    → c_int16
#     TYPE       → INT32    → c_int32      (parking type enum)
#     SUFFIX     → STRING8  → c_char * 8   (L / C / R / empty)
#   CLOSE PARKING
#   CLOSE AIRPORT

class _AirportData(ctypes.Structure):
    _pack_   = 1
    _layout_ = "ms"
    _fields_ = [
        ("latitude",  ctypes.c_double),
        ("longitude", ctypes.c_double),
    ]

class _RunwayData(ctypes.Structure):
    _pack_   = 1
    _layout_ = "ms"
    _fields_ = [
        ("ident",       ctypes.c_char * 8),
        ("sec_ident",   ctypes.c_char * 8),
        ("lat",         ctypes.c_double),
        ("lon",         ctypes.c_double),
        ("sec_lat",     ctypes.c_double),
        ("sec_lon",     ctypes.c_double),
    ]

class _ParkingData(ctypes.Structure):
    _pack_   = 1
    _layout_ = "ms"
    _fields_ = [
        ("latitude",  ctypes.c_double),
        ("longitude", ctypes.c_double),
        ("heading",   ctypes.c_float),
        ("name",      ctypes.c_char * 8),
        ("number",    ctypes.c_int16),
        ("type",      ctypes.c_int32),
        ("suffix",    ctypes.c_char * 8),
    ]

# ── result types ──────────────────────────────────────────────────────────────

class ParkingSpot:
    """One parking position at an airport (gate, stand, tiedown, etc.)."""

    def __init__(self, name, number, park_type, suffix, lat, lon, heading):
        """
        name      — raw NAME field from SimConnect (e.g. b'GATE_F')
        number    — integer gate/stand number
        park_type — integer parking type code (_PARK_* constant)
        suffix    — L, C, R, or empty
        """
        self.lat     = lat
        self.lon     = lon
        self.heading = heading
        self._name   = name.decode(errors="replace").strip("\x00 ")
        self._number = number
        self._type   = park_type
        self._suffix = suffix.decode(errors="replace").strip("\x00 ")

    @property
    def label(self):
        """Human-readable label, e.g. 'Gate F32' or 'Ramp 7'."""
        type_str = _PARK_LABELS.get(self._type, "Parking")
        parts = [type_str]
        if self._name:
            # Strip redundant type prefix if present (GATE_F → F, RAMP_GA → skip)
            clean = self._name.replace("GATE_", "").replace("RAMP_", "").strip("_")
            if clean and clean not in ("GA", "CARGO"):
                parts.append(clean)
        if self._number and self._number > 0:
            parts.append(str(self._number))
        if self._suffix:
            parts[-1] += self._suffix
        return " ".join(parts)


class RunwayEnd:
    """One threshold end of a runway."""

    def __init__(self, designator, lat, lon):
        """
        designator — string like '27L' or '09R'
        lat, lon   — threshold position
        """
        self.designator = designator
        self.lat        = lat
        self.lon        = lon


class AirportFacilities:
    """Cached facilities data for one airport."""

    def __init__(self, icao):
        """Initialise with empty lists; populated by FacilitiesClient."""
        self.icao     = icao
        self.runways  = []   # list of RunwayEnd
        self.parking  = []   # list of ParkingSpot
        self.complete = False

    def nearest_parking(self, lat, lon):
        """Return the closest ParkingSpot, or None."""
        if not self.parking:
            return None
        return min(self.parking, key=lambda p: _dist(lat, lon, p.lat, p.lon))

    def nearest_runway(self, lat, lon, heading_deg):
        """
        Return the RunwayEnd whose threshold is closest to the aircraft AND
        whose heading matches the aircraft heading within 45°.
        Falls back to heading-only if no threshold data available.
        """
        if not self.runways:
            return None
        candidates = [
            r for r in self.runways
            if abs(_angle_diff(_designator_heading(r.designator), heading_deg)) < 45
        ]
        if not candidates:
            candidates = self.runways
        return min(candidates, key=lambda r: _dist(lat, lon, r.lat, r.lon))

    def active_runways(self, wind_direction_deg, wind_speed_kt=0):
        """
        Return runway ends that face into the wind.

        Returns an empty list for calm winds (< 3 kt) — any runway is valid.
        Otherwise returns all ends within 90° of the wind direction, sorted
        by alignment (most favourable first).
        """
        if not self.runways or wind_speed_kt < 3:
            return []
        candidates = [
            r for r in self.runways
            if abs(_angle_diff(_designator_heading(r.designator), wind_direction_deg)) < 90
        ]
        return sorted(
            candidates,
            key=lambda r: abs(_angle_diff(_designator_heading(r.designator), wind_direction_deg)),
        )


# ── geometry helpers ──────────────────────────────────────────────────────────

def _dist(lat1, lon1, lat2, lon2):
    """Fast approximate distance in degrees² (good enough for sorting)."""
    dlat = lat2 - lat1
    dlon = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return dlat * dlat + dlon * dlon


def _angle_diff(a, b):
    """Signed difference between two headings, in (-180, 180]."""
    d = (a - b) % 360
    return d - 360 if d > 180 else d


def _designator_heading(des):
    """Return the nominal magnetic heading for a runway designator like '27L'."""
    try:
        num = int("".join(c for c in des if c.isdigit()))
        return (num % 36) * 10
    except Exception:
        return 0


# ── main client class ─────────────────────────────────────────────────────────

class FacilitiesClient:
    """
    Fetches and caches SimConnect Facilities data for nearby airports.

    Thread model: one background thread owns the SimConnect connection and
    processes all messages.  The public methods are safe to call from any
    thread; they read from a threading.Lock-protected dict.
    """

    APP_NAME = b"FlightInstructor_Facilities"

    def __init__(self):
        """Create a disconnected client."""
        self._dll     = None
        self._handle  = None
        self._thread  = None
        self._running = False
        self._lock    = threading.Lock()
        self._cache   = {}          # icao -> AirportFacilities
        self._pending = set()       # icao -> request in flight

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self):
        """
        Open a dedicated SimConnect connection for facilities queries.

        Safe to call even when MSFS is not running; returns False and logs
        a warning rather than raising.
        """
        if not _ON_WINDOWS:
            return False
        dll = self._load_dll()
        if dll is None:
            return False
        handle = ctypes.c_void_p()
        hr = dll.SimConnect_Open(
            ctypes.byref(handle),
            self.APP_NAME,
            None, 0, None, 0,
        )
        if hr != 0:
            log.warning("FacilitiesClient: SimConnect_Open failed (hr=%08x)", hr)
            return False
        self._dll    = dll
        self._handle = handle
        self._define_facility()
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True, name="FacilitiesDispatch")
        self._thread.start()
        log.info("FacilitiesClient connected")
        return True

    def disconnect(self):
        """Close the facilities SimConnect connection."""
        self._running = False
        if self._dll and self._handle:
            try:
                self._dll.SimConnect_Close(self._handle)
            except Exception:
                pass
        self._dll    = None
        self._handle = None

    # ------------------------------------------------------------------
    # Public data API (thread-safe)
    # ------------------------------------------------------------------

    def request_airport(self, icao):
        """
        Trigger an async facilities fetch for *icao*.

        The result is available via nearest_parking / nearest_runway once
        the background dispatch processes the response (typically < 1 s).
        """
        if not self._running or not icao:
            return
        with self._lock:
            if icao in self._cache or icao in self._pending:
                return
            self._pending.add(icao)
        self._send_request(icao)

    def nearest_parking(self, lat, lon, icao):
        """Return the closest ParkingSpot for *icao*, or None."""
        fac = self._get_cache(icao)
        return fac.nearest_parking(lat, lon) if fac else None

    def nearest_runway(self, lat, lon, heading_deg, icao):
        """Return the closest matching RunwayEnd for *icao*, or None."""
        fac = self._get_cache(icao)
        return fac.nearest_runway(lat, lon, heading_deg) if fac else None

    def has_data(self, icao):
        """Return True once facilities data for *icao* is fully received."""
        fac = self._get_cache(icao)
        return fac is not None and fac.complete

    def active_runways(self, icao, wind_direction_deg, wind_speed_kt=0):
        """Return into-wind runway ends for *icao*, or an empty list."""
        fac = self._get_cache(icao)
        if fac is None or not fac.complete:
            return []
        return fac.active_runways(wind_direction_deg, wind_speed_kt)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_dll(self):
        """Find and load SimConnect.dll from the Python-SimConnect package."""
        try:
            import SimConnect as _pkg
            path = os.path.join(os.path.dirname(_pkg.__file__), "SimConnect.dll")
            if os.path.exists(path):
                return ctypes.windll.LoadLibrary(path)
        except Exception as exc:
            log.debug("FacilitiesClient: could not load SimConnect.dll: %s", exc)
        return None

    def _define_facility(self):
        """
        Register the facility definition with SimConnect.

        Field order determines the binary layout of the response payload.
        Each AddToFacilityDefinition call appends one field to the definition.
        """
        add = self._dll.SimConnect_AddToFacilityDefinition
        h   = self._handle
        d   = _DEF_AIRPORT

        # Airport header fields
        add(h, d, b"OPEN AIRPORT")
        add(h, d, b"LATITUDE")
        add(h, d, b"LONGITUDE")

        # Runway sub-records (one per runway end pair)
        add(h, d, b"OPEN RUNWAY")
        add(h, d, b"IDENT")
        add(h, d, b"SECONDARY_IDENT")
        add(h, d, b"LATITUDE")
        add(h, d, b"LONGITUDE")
        add(h, d, b"SECONDARY_LATITUDE")
        add(h, d, b"SECONDARY_LONGITUDE")
        add(h, d, b"CLOSE RUNWAY")

        # Parking sub-records (one per parking spot)
        add(h, d, b"OPEN PARKING")
        add(h, d, b"LATITUDE")
        add(h, d, b"LONGITUDE")
        add(h, d, b"HEADING")
        add(h, d, b"NAME")
        add(h, d, b"NUMBER")
        add(h, d, b"TYPE")
        add(h, d, b"SUFFIX")
        add(h, d, b"CLOSE PARKING")

        add(h, d, b"CLOSE AIRPORT")

    def _send_request(self, icao):
        """Ask SimConnect to deliver facility data for *icao*."""
        try:
            self._dll.SimConnect_RequestFacilityData(
                self._handle,
                _DEF_AIRPORT,
                _REQ_AIRPORT,
                icao.encode() if isinstance(icao, str) else icao,
                b"",
            )
        except Exception as exc:
            log.warning("FacilitiesClient: request_airport(%s) failed: %s", icao, exc)
            with self._lock:
                self._pending.discard(icao)

    # ------------------------------------------------------------------
    # Background dispatch thread
    # ------------------------------------------------------------------

    def _run(self):
        """Dispatch loop — runs in the background thread."""
        if not _ON_WINDOWS:
            return
        _DispatchProc = ctypes.WINFUNCTYPE(
            None,
            ctypes.POINTER(_RecvBase),
            ctypes.c_uint32,
            ctypes.c_void_p,
        )
        cb = _DispatchProc(self._dispatch)
        while self._running:
            try:
                self._dll.SimConnect_CallDispatch(self._handle, cb, None)
            except Exception as exc:
                log.debug("FacilitiesClient dispatch error: %s", exc)
                break
            # Small sleep keeps CPU usage negligible; we're not time-critical
            import time
            time.sleep(0.05)

    def _dispatch(self, pData, cbData, pContext):
        """SimConnect dispatch callback — called from the background thread."""
        try:
            recv = ctypes.cast(pData, ctypes.POINTER(_RecvBase)).contents
            if recv.dwID == _RECV_ID_FACILITY_DATA:
                self._on_facility_data(pData, cbData)
            elif recv.dwID == _RECV_ID_FACILITY_END:
                self._on_facility_end(pData)
            elif recv.dwID == _RECV_ID_QUIT:
                self._running = False
        except Exception as exc:
            log.debug("FacilitiesClient._dispatch error: %s", exc)

    def _on_facility_data(self, pData, cbData):
        """Parse one SIMCONNECT_RECV_FACILITY_DATA message."""
        hdr = ctypes.cast(pData, ctypes.POINTER(_RecvFacilityData)).contents
        # The variable payload starts immediately after the fixed header
        payload_offset = ctypes.sizeof(_RecvFacilityData)
        raw = (ctypes.c_uint8 * cbData).from_address(
            ctypes.addressof(pData.contents) + payload_offset
            if hasattr(pData, "contents") else ctypes.cast(pData, ctypes.c_void_p).value + payload_offset
        )
        buf = bytes(raw)

        # Find which airport this data belongs to by looking at pending requests
        # (we only ever have one in-flight request at a time for simplicity)
        with self._lock:
            icao = next(iter(self._pending), None)
            if icao is None:
                return
            if icao not in self._cache:
                self._cache[icao] = AirportFacilities(icao)
            fac = self._cache[icao]

        if hdr.Type == _FAC_AIRPORT:
            self._parse_airport(buf, fac)
        elif hdr.Type == _FAC_RUNWAY:
            self._parse_runway(buf, fac)
        elif hdr.Type == _FAC_PARKING:
            self._parse_parking(buf, fac)

    def _on_facility_end(self, pData):
        """Mark the airport as complete and remove from pending."""
        with self._lock:
            icao = next(iter(self._pending), None)
            if icao and icao in self._cache:
                self._cache[icao].complete = True
                self._pending.discard(icao)
                log.info(
                    "FacilitiesClient: %s loaded — %d runways, %d parking spots",
                    icao,
                    len(self._cache[icao].runways),
                    len(self._cache[icao].parking),
                )

    def _parse_airport(self, buf, fac):
        """Extract airport-level fields (lat/lon — mainly informational)."""
        if len(buf) < ctypes.sizeof(_AirportData):
            return
        data = _AirportData.from_buffer_copy(buf)
        fac.latitude  = data.latitude
        fac.longitude = data.longitude

    def _parse_runway(self, buf, fac):
        """Extract one runway end pair and add both ends to fac.runways."""
        if len(buf) < ctypes.sizeof(_RunwayData):
            return
        data = _RunwayData.from_buffer_copy(buf)

        primary   = data.ident.decode(errors="replace").strip("\x00 ")
        secondary = data.sec_ident.decode(errors="replace").strip("\x00 ")

        if primary:
            fac.runways.append(RunwayEnd(primary,   data.lat,     data.lon))
        if secondary:
            fac.runways.append(RunwayEnd(secondary, data.sec_lat, data.sec_lon))

    def _parse_parking(self, buf, fac):
        """Extract one parking spot and add it to fac.parking."""
        if len(buf) < ctypes.sizeof(_ParkingData):
            return
        data = _ParkingData.from_buffer_copy(buf)
        fac.parking.append(ParkingSpot(
            name      = data.name,
            number    = data.number,
            park_type = data.type,
            suffix    = data.suffix,
            lat       = data.latitude,
            lon       = data.longitude,
            heading   = data.heading,
        ))

    def _get_cache(self, icao):
        """Thread-safe cache lookup. Returns AirportFacilities or None."""
        with self._lock:
            return self._cache.get(icao)
