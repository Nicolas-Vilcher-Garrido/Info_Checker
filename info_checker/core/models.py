from dataclasses import dataclass
from typing import Any, Dict, Optional, List

@dataclass
class CollectRequest:
    source: str               # ex: URL, janela/app, seletor
    selector: Optional[str] = None  # css/xpath (quando aplicável)
    method: str = "GET"
    extra: Dict[str, Any] = None

@dataclass
class CollectResponse:
    raw: Any                  # html/texto/img etc.
    extracted: Optional[str]  # valor "final" extraído (ex.: preço)
    meta: Dict[str, Any]

@dataclass
class ValidationRule:
    type: str                 # "equals", "regex", "range", "tolerance"
    expected: Any
    params: Dict[str, Any] = None

@dataclass
class Task:
    id: str
    collector: str            # "http", "playwright", "desktop"
    request: CollectRequest
    extraction: Dict[str, Any]  # {strategy: "css"|"xpath"|"regex", path/pattern}
    rules: List[ValidationRule]
