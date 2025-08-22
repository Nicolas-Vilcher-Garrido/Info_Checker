# info_checker/core/runner.py
import json
from typing import Any, Dict

from .models import Task
from .interfaces import Collector
from ..collectors.http_requests import HttpCollector, simple_bs_extract  # se você tiver esse coletor
from ..collectors.playwright_browser import PlaywrightCollector


class Runner:
    def __init__(self, cfg_collectors: Dict[str, Any] | None = None):
        cfg_collectors = cfg_collectors or {}
        # instância dos coletores disponíveis
        self.collectors: Dict[str, Collector] = {
            "http": HttpCollector(timeout=cfg_collectors.get("http", {}).get("timeout", 25)),
            "playwright": PlaywrightCollector(
                headless=cfg_collectors.get("playwright", {}).get("headless", True),
                default_timeout_ms=cfg_collectors.get("playwright", {}).get("timeout_ms", 20000),
            ),
        }

    def run_task(self, task: Task) -> Dict[str, Any]:
        if task.collector not in self.collectors:
            raise KeyError(f"Collector '{task.collector}' não registrado.")

        collector = self.collectors[task.collector]
        col_resp = collector.collect(task.request)

        strategy = (task.extraction or {}).get("strategy", "none")
        value = None

        # ---- Estratégias de extração ----
        if strategy in (None, "", "none"):
            # Nada a extrair/validar: devolve meta e segue ok (a não ser que haja rules)
            value = None
        elif strategy == "css":
            # Exemplo: usar simple_bs_extract se vier path
            path = task.extraction.get("path")
            if not path:
                raise ValueError("extraction.strategy=css exige 'path'")
            value = simple_bs_extract(col_resp.raw, path)
        elif strategy == "regex":
            import re
            pattern = task.extraction.get("pattern")
            if not pattern:
                raise ValueError("extraction.strategy=regex exige 'pattern'")
            m = re.search(pattern, col_resp.raw or "", flags=re.DOTALL | re.IGNORECASE)
            value = m.group(1) if m and m.groups() else (m.group(0) if m else None)
        else:
            raise ValueError(f"Extraction strategy not supported: {strategy}")

        # ---- Validações ----
        validations = []
        rules = task.rules or []
        ok = True

        for r in rules:
            if r.type == "regex":
                import re
                got_str = "" if value is None else str(value)
                passed = re.search(r.expected, got_str) is not None
                validations.append({"rule": "regex", "ok": passed, "pattern": r.expected, "got": value})
                ok = ok and passed
            elif r.type == "tolerance":
                try:
                    target = float(r.expected.get("target"))
                    pct = float(r.expected.get("pct", 0.05))
                    got_val = float(value) if value is not None else float("nan")
                    lower = target * (1 - pct)
                    upper = target * (1 + pct)
                    passed = (lower <= got_val <= upper)
                    validations.append({
                        "rule": "tolerance", "ok": passed, "target": target, "pct": pct, "got": value
                    })
                    ok = ok and passed
                except Exception:
                    validations.append({"rule": "tolerance", "ok": False, "error": "invalid numeric conversion", "got": value})
                    ok = False
            else:
                validations.append({"rule": r.type, "ok": False, "error": "unsupported rule"})
                ok = False

        # Se não tem rules e strategy=none, consideramos ok=True (uso típico: apenas exportação)
        if not rules and strategy in (None, "", "none"):
            ok = True

        return {
            "task_id": task.id,
            "ok": ok,
            "value": value,
            "validations": validations,
            "meta": {
                **(col_resp.meta or {}),
            },
        }
