from abc import ABC, abstractmethod
from .models import CollectRequest, CollectResponse

class Collector(ABC):
    @abstractmethod
    def collect(self, req: CollectRequest) -> CollectResponse:
        ...

class Extractor(ABC):
    @abstractmethod
    def extract(self, raw: any, extraction_cfg: dict) -> str:
        ...
