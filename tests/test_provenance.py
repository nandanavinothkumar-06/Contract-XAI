import pytest
from src.adapters.registry import registry

def test_cuad_provenance():
    adapter = registry.get("CUAD")()
    assert "CC BY 4.0" in adapter.license_status
    assert "underlying contract rights remain subject to" in adapter.license_status
    assert adapter.access_status == "Open download"

def test_claudette_provenance():
    adapter = registry.get("CLAUDETTE")()
    assert adapter.license_status == "Not explicitly verified from authoritative source"

def test_construction_provenance():
    adapter = registry.get("CONSTRUCTION_BASE")()
    assert adapter.access_status == "Unresolved / not independently verified"
    assert adapter.license_status == "Not verified"
