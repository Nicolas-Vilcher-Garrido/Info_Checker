import re
from typing import Any, Dict

def validate_equals(value: str, expected: Any, params: Dict):
    ok = str(value) == str(expected)
    return ok, {"expected": expected, "got": value}

def validate_regex(value: str, expected_pattern: str, params: Dict):
    ok = re.search(expected_pattern, value or "") is not None
    return ok, {"pattern": expected_pattern, "got": value}

def _to_float(s):
    if s is None: 
        return None
    # normaliza: remove moeda/espaco/ponto milhar, troca vírgula por ponto
    s = str(s)
    s = s.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def validate_range(value: str, expected: Dict, params: Dict):
    v = _to_float(value)
    mn, mx = expected.get("min"), expected.get("max")
    ok = (v is not None) and (mn is None or v >= mn) and (mx is None or v <= mx)
    return ok, {"range": expected, "got": v}

def validate_tolerance(value: str, expected: Dict, params: Dict):
    v = _to_float(value)
    target, pct = expected["target"], expected.get("pct", 0.01)
    if v is None:
        return False, {"error": "value_not_numeric", "got": value}
    low, high = target * (1 - pct), target * (1 + pct)
    ok = low <= v <= high
    return ok, {"target": target, "pct": pct, "interval": [low, high], "got": v}

VALIDATORS = {
    "equals": validate_equals,
    "regex": validate_regex,
    "range": validate_range,
    "tolerance": validate_tolerance,
}
