import requests
from bs4 import BeautifulSoup
from ..core.interfaces import Collector
from ..core.models import CollectRequest, CollectResponse

class HttpCollector(Collector):
    def __init__(self, headers=None, timeout=20):
        self.headers = headers or {"User-Agent": "InfoChecker/1.0"}
        self.timeout = timeout

    def collect(self, req: CollectRequest) -> CollectResponse:
        resp = requests.request(req.method, req.source, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        return CollectResponse(raw=resp.text, extracted=None, meta={"status": resp.status_code})

def simple_bs_extract(html: str, extraction_cfg: dict) -> str:
    soup = BeautifulSoup(html, "html.parser")
    strat = extraction_cfg.get("strategy", "css")
    if strat != "css":
        raise ValueError("Unsupported extraction strategy for HTTP: %s" % strat)
    path = extraction_cfg["path"]
    el = soup.select_one(path)
    return el.get_text(strip=True) if el else None
