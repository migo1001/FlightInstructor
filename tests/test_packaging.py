"""
Smoke tests that verify the package ships with all required data files.
These catch regressions where pyproject.toml package-data entries are missing
or the rules directory is moved without updating the path resolution.
"""

from pathlib import Path

import flight_instructor
from flight_instructor.__main__ import _rules_dir
from flight_instructor.session import Session


class TestRulesShippedWithPackage:
    def _rules(self):
        return Path(flight_instructor.__file__).parent / "rules"

    def test_rules_directory_exists(self):
        assert self._rules().is_dir()

    def test_global_lua_present(self):
        assert (self._rules() / "global.lua").exists()

    def test_c172_lua_present(self):
        assert (self._rules() / "c172.lua").exists()


class TestSessionLoadsFromPackage:
    def test_session_initialises_without_error(self):
        """Session.__init__ loads both rule files; an exception means rules are missing."""
        Session(_rules_dir())
