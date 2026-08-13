import json
import uuid
from datetime import date, timedelta

from config import MEMO_FILE

# 分类 → 颜色映射
CATEGORY_COLORS = {
    "work": "#e53935",
    "personal": "#2ca02c",
    "health": "#ff9800",
    "other": "#9e9e9e",
}
CATEGORY_LABELS = {
    "work": "工作",
    "personal": "个人",
    "health": "健康",
    "other": "其他",
}
# 优先级 → 排序权重和标记
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PRIORITY_LABELS = {"high": "高", "medium": "中", "low": "低"}

REPEAT_OPTIONS = {
    "none": "不重复",
    "daily": "每天",
    "weekly": "每周",
    "monthly": "每月",
}


def _normalize_memo(m):
    """将旧格式备忘录项迁移到新格式。"""
    if not isinstance(m, dict):
        return None
    m.setdefault("id", str(uuid.uuid4())[:8])
    m.setdefault("time", "")
    m.setdefault("text", "")
    m.setdefault("category", "other")
    m.setdefault("priority", "medium")
    m.setdefault("done", False)
    m.setdefault("remind_before", 0)
    m.setdefault("repeat", "none")
    m.setdefault("snooze_until", 0)  # 稍后提醒截止时间戳（秒），0=未暂缓（非重复备忘用）
    m.setdefault("completed_dates", [])  # 已完成日期列表（重复备忘按日期独立）
    m.setdefault("snoozed_dates", {})   # 稍后提醒时间戳字典（重复备忘按日期独立）
    return m


# 内存缓存：避免每次 load_memos() 都读磁盘 JSON
_memo_cache = None
_memo_cache_mtime = 0


def _invalidate_memo_cache():
    """强制下一次 load_memos() 重新从磁盘读取。"""
    global _memo_cache, _memo_cache_mtime
    _memo_cache = None
    _memo_cache_mtime = 0


def load_memos():
    global _memo_cache, _memo_cache_mtime
    if MEMO_FILE.exists():
        mtime = MEMO_FILE.stat().st_mtime
    else:
        mtime = 0
    # 文件未变且缓存有效则直接返回
    if _memo_cache is not None and mtime == _memo_cache_mtime:
        return _memo_cache
    if not MEMO_FILE.exists():
        _memo_cache = {}
        _memo_cache_mtime = 0
        return {}
    try:
        with open(MEMO_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        fixed = {}
        migrated = False
        for k, v in raw.items():
            if isinstance(v, str):
                fixed[k] = [_normalize_memo({"time": "", "text": v})]
                migrated = True
            elif isinstance(v, list):
                normalized = []
                for item in v:
                    nm = _normalize_memo(item)
                    if nm:
                        normalized.append(nm)
                        if "category" not in item or "priority" not in item or "done" not in item:
                            migrated = True
                fixed[k] = normalized
        if migrated:
            _write_memo_atomic(fixed)
        _memo_cache = fixed
        _memo_cache_mtime = MEMO_FILE.stat().st_mtime if MEMO_FILE.exists() else 0
        return fixed
    except Exception:
        _memo_cache = {}
        _memo_cache_mtime = 0
        return {}


def _write_memo_atomic(data: dict):
    """原子写入：先写临时文件再 rename，防止断电截断导致全部数据丢失。"""
    tmp = MEMO_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(MEMO_FILE)
    except Exception as e:
        print(f"[备忘录] 原子写入失败: {e}")
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def save_day_memos(d: date, memo_list):
    memos = load_memos()
    key = d.strftime("%Y-%m-%d")
    if not memo_list:
        if key in memos:
            del memos[key]
    else:
        memos[key] = memo_list
    _write_memo_atomic(memos)
    # 更新内存缓存 + mtime，避免下次 load_memos() 重读磁盘
    global _memo_cache, _memo_cache_mtime
    _memo_cache = memos
    _memo_cache_mtime = MEMO_FILE.stat().st_mtime if MEMO_FILE.exists() else 0


def get_day_memos(d: date):
    memos = load_memos()
    key = d.strftime("%Y-%m-%d")
    return memos.get(key, [])


def get_sorted_memos(memo_list):
    """按优先级排序备忘录列表（高→中→低），返回新列表。"""
    return sorted(memo_list, key=lambda m: PRIORITY_ORDER.get(m.get("priority", "medium"), 1))


def get_effective_memos_for_date(d: date):
    """获取某天的有效备忘录，包括重复备忘的展开。
    重复备忘的 done / snooze 按日期独立（completed_dates / snoozed_dates），
    非重复备忘使用全局 done / snooze_until。
    """
    import time
    now_ts = time.time()
    today_str = d.strftime("%Y-%m-%d")
    memos = load_memos()
    result = []
    # 当天直接备忘
    for m in memos.get(today_str, []):
        # 非重复备忘：检查全局 snooze_until
        if m.get("repeat", "none") == "none" and m.get("snooze_until", 0) > now_ts:
            continue
        result.append(dict(m))
    # 检查所有日期的重复备忘
    for raw_key, memo_list in memos.items():
        try:
            raw_date = date.fromisoformat(raw_key)
        except (ValueError, TypeError):
            continue
        if raw_date == d:
            continue  # 已处理
        for m in memo_list:
            repeat = m.get("repeat", "none")
            if repeat == "none":
                continue
            # 检查是否该日期展开
            if not (repeat == "daily"
                    or (repeat == "weekly" and raw_date.weekday() == d.weekday())
                    or (repeat == "monthly" and raw_date.day == d.day)):
                continue
            # 重复备忘：按日期检查 snooze
            snoozed = m.get("snoozed_dates", {})
            if snoozed.get(today_str, 0) > now_ts:
                continue
            # 复制并覆盖 done / snooze_until 为当前日期的值
            copy = dict(m)
            copy["done"] = today_str in m.get("completed_dates", [])
            copy["snooze_until"] = snoozed.get(today_str, 0)
            result.append(copy)
    return get_sorted_memos(result)
