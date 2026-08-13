import json
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal

from config import HOLIDAY_CACHE_FILE

# ===== 中国法定节假日数据（联网下载 + 本地缓存） =====
# 数据结构：{ "2026": {"01-01": {"name":"元旦","holiday":true}, "02-04": {"name":"春节","holiday":false}, ... } }
# holiday=true 表示休息日，holiday=false 表示调休上班日
_HOLIDAY_CACHE = {}  # 内存缓存：year(str) -> {MM-DD: {...}}
_DOWNLOAD_FAILED = set()  # 下载失败的年份集合，本次运行内不再重试

def _download_year_holidays(year: int):
    """从 timor.tech 下载指定年的节假日安排。失败返回 None。"""
    url = f"https://timor.tech/api/holiday/year/{year}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != 0:
            return None
        holiday_map = data.get("holiday", {})
        if not isinstance(holiday_map, dict):
            return None
        # 转成简化结构：{ "MM-DD": {"name":..., "holiday": True/False} }
        result = {}
        for mmdd, info in holiday_map.items():
            if not isinstance(info, dict):
                continue
            result[mmdd] = {
                "name": info.get("name", ""),
                "holiday": bool(info.get("holiday", False)),
            }
        return result
    except Exception as e:
        print(f"[节假日] 下载 {year} 年失败: {e}")
        return None

def _save_holiday_cache(all_cache: dict):
    try:
        with open(HOLIDAY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[节假日] 缓存写入失败: {e}")

def _load_holiday_cache_file():
    """从磁盘加载缓存。返回 dict。"""
    if HOLIDAY_CACHE_FILE.exists():
        try:
            with open(HOLIDAY_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def get_year_holidays(year: int, allow_download=True):
    """获取指定年的节假日数据。优先内存→磁盘→联网下载。"""
    key = str(year)
    if key in _HOLIDAY_CACHE:
        return _HOLIDAY_CACHE[key]
    # 从磁盘加载
    disk = _load_holiday_cache_file()
    if key in disk:
        _HOLIDAY_CACHE[key] = disk[key]
        return disk[key]
    # 联网下载
    if allow_download and year not in _DOWNLOAD_FAILED:
        downloaded = _download_year_holidays(year)
        if downloaded is not None:
            _HOLIDAY_CACHE[key] = downloaded
            disk[key] = downloaded
            _save_holiday_cache(disk)
            return downloaded
        else:
            # 标记该年下载失败，本次运行内不再重试，避免每次渲染都等超时
            _DOWNLOAD_FAILED.add(year)
    return None

def is_download_failed(year: int) -> bool:
    """该年份是否已在本次运行中标记为下载失败。"""
    return year in _DOWNLOAD_FAILED


def clear_download_failed(year: int = None):
    """清除下载失败标记。不传 year 则清除所有年份。"""
    if year is None:
        _DOWNLOAD_FAILED.clear()
    else:
        _DOWNLOAD_FAILED.discard(year)

class HolidayDownloadThread(QThread):
    """后台下载节假日数据的线程，避免阻塞 UI。"""
    download_done = Signal(int)   # 下载完成，参数为年份
    download_failed = Signal(int) # 下载失败，参数为年份

    def __init__(self, year: int):
        super().__init__()
        self._year = year

    def run(self):
        if str(self._year) in _HOLIDAY_CACHE:
            return
        if self._year in _DOWNLOAD_FAILED:
            return
        downloaded = _download_year_holidays(self._year)
        if downloaded is not None:
            _HOLIDAY_CACHE[str(self._year)] = downloaded
            disk = _load_holiday_cache_file()
            disk[str(self._year)] = downloaded
            _save_holiday_cache(disk)
            self.download_done.emit(self._year)
        else:
            _DOWNLOAD_FAILED.add(self._year)
            self.download_failed.emit(self._year)
