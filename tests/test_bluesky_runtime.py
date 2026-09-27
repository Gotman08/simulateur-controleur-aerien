"""Clock regressions without importing the optional BlueSky engine."""
from types import SimpleNamespace
from unittest.mock import Mock

import bluesky_runtime as runtime


def test_empty_initial_simulator_does_not_spin(monkeypatch):
    engine = SimpleNamespace(INIT=0, sim=SimpleNamespace(state=0, simt=0, step=Mock()),
                             traf=SimpleNamespace(ntraf=0), stack=SimpleNamespace(process=Mock()))
    monkeypatch.setattr(runtime, "bs", lambda: engine)
    assert runtime.advance(1) == 0
    engine.sim.step.assert_not_called()


def test_creating_aircraft_does_not_advance_physics(monkeypatch):
    engine = SimpleNamespace(stack=SimpleNamespace(stack=Mock(), process=Mock()))
    monkeypatch.setattr(runtime, "bs", lambda: engine)
    monkeypatch.setattr(runtime, "advance", Mock(side_effect=AssertionError("clock advanced")))
    runtime.create("AFR1", "A320", 49, 4, 90, 30000, 250)
    engine.stack.stack.assert_called_once_with("CRE AFR1 A320 49 4 90 30000 250")
    engine.stack.process.assert_called_once()
