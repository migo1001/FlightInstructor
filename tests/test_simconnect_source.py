import sys
import types

import pytest

from flight_instructor.simconnect_source import SimConnectSource


class TestSimConnectConnect:
    def test_aircraft_requests_failure_disconnects_partial_simconnect(self, monkeypatch):
        module = types.ModuleType("SimConnect")
        simconnect_instances = []

        class FakeSimConnect:
            def __init__(self):
                self.exited = False
                simconnect_instances.append(self)

            def exit(self):
                self.exited = True

        class FailingAircraftRequests:
            def __init__(self, _sm, _time):
                raise RuntimeError("request setup failed")

        module.SimConnect = FakeSimConnect
        module.AircraftRequests = FailingAircraftRequests
        monkeypatch.setitem(sys.modules, "SimConnect", module)

        source = SimConnectSource()

        with pytest.raises(RuntimeError, match="request setup failed"):
            source.connect()

        assert simconnect_instances[0].exited is True
        assert source.is_connected() is False
        assert source._sm is None
        assert source._aq is None
