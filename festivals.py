from datetime import date

from lunar import solar_to_lunar, format_lunar_day
from holiday import get_year_holidays

# 公历节日名（仅显示，不决定休息）—— 教师节、儿童节等不放假节日
SOLAR_FESTIVAL_NAMES = {
    (1,1): "元旦",(2,14): "情人节",(3,8): "妇女节",(3,12): "植树节",
    (4,1): "愚人节",(5,4): "青年节",(6,1): "儿童节",
    (7,1): "建党节",(8,1): "建军节",(9,10): "教师节",(12,25): "圣诞节",
}
# 农历节日名（仅显示，不决定休息）—— 七夕、重阳等不放假节日
LUNAR_FESTIVAL_NAMES = {
    (1,15): "元宵节",(2,2): "龙抬头",(7,7): "七夕节",(9,9): "重阳节",
    (12,8): "腊八节",(12,23): "小年",
}

def get_day_extra_info(d: date):
    """返回 (显示文本, is_rest_day, is_holiday_name, is_workday_adjust)。
    - is_rest_day=True：法定假日 or 普通周末（且不是调休上班）→ 标红
    - is_holiday_name=True：显示的是节日名（用于加粗样式）
    - is_workday_adjust=True：调休上班日（原本是周末，但要上班）→ "班"字需显眼红色
    """
    year_data = get_year_holidays(d.year, allow_download=False) or {}
    mmdd = f"{d.month:02d}-{d.day:02d}"
    official = year_data.get(mmdd)

    is_weekend = d.weekday() >= 5

    # 1) 法定假日（放假）
    if official and official.get("holiday"):
        return official.get("name", "休"), True, True, False
    # 2) 调休上班日（原本是周末，但要上班）
    if official and not official.get("holiday"):
        # 显示"班"标记 + 农历/节日
        lunar = solar_to_lunar(d)
        lunar_text = format_lunar_day(lunar) if lunar else ""
        # 看是否撞上节日名
        festival = SOLAR_FESTIVAL_NAMES.get((d.month, d.day))
        if not festival and lunar and not lunar[3]:
            festival = LUNAR_FESTIVAL_NAMES.get((lunar[1], lunar[2]))
        display = festival if festival else lunar_text
        return f"班·{display}" if display else "班", False, False, True
    # 3) 普通周末
    if is_weekend:
        lunar = solar_to_lunar(d)
        lunar_text = format_lunar_day(lunar) if lunar else ""
        festival = SOLAR_FESTIVAL_NAMES.get((d.month, d.day))
        if not festival and lunar and not lunar[3]:
            festival = LUNAR_FESTIVAL_NAMES.get((lunar[1], lunar[2]))
        if festival:
            return festival, True, True, False
        return lunar_text, True, False, False
    # 4) 普通工作日：显示节日名（如果有）或农历
    festival = SOLAR_FESTIVAL_NAMES.get((d.month, d.day))
    if festival:
        return festival, False, True, False
    lunar = solar_to_lunar(d)
    if lunar:
        if not lunar[3]:
            lunar_fest = LUNAR_FESTIVAL_NAMES.get((lunar[1], lunar[2]))
            if lunar_fest:
                return lunar_fest, False, True, False
        return format_lunar_day(lunar), False, False, False
    return "", False, False, False
