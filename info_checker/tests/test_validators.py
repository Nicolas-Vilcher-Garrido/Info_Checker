from info_checker.core.validators import validate_tolerance

def test_tolerance():
    ok, meta = validate_tolerance("R$ 1.300,00", {"target": 1299.90, "pct": 0.05}, {})
    assert ok
