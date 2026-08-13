import os
import platform
import warnings
from pathlib import Path

from PySide6.QtCore import QSettings

if platform.system() == "Windows":
    os.environ["QT_QPA_PLATFORM"] = "windows"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
warnings.filterwarnings("ignore")

MEMO_FILE = Path(__file__).resolve().parent / "calendar_memo.json"
HOLIDAY_CACHE_FILE = Path(__file__).resolve().parent / "holiday_cache.json"
SETTING_FILE = QSettings("CalendarDesk", "CalendarMemo")
