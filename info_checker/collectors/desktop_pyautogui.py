try:
    import pyautogui
except Exception:
    pyautogui = None

import time
from ..core.interfaces import Collector
from ..core.models import CollectRequest, CollectResponse

class DesktopCollector(Collector):
    def collect(self, req: CollectRequest) -> CollectResponse:
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI não está instalado no ambiente.")
        time.sleep(0.5)
        screenshot = pyautogui.screenshot()  # PIL Image
        return CollectResponse(raw=screenshot, extracted=None, meta={"source": "desktop"})
