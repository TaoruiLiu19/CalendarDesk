from datetime import date

# ===== 农历转换模块（1900-2100） =====
# 数据格式：每年一个整数，二进制位含义：
# bit[15:4] = 12 个农历月的大小（1=大月30天，0=小月29天）
#   正月=bit15, 二月=bit14, ..., 腊月=bit4（即 bit (16-month)）
# bit[3:0]  = 闰月月份（0 表示无闰月），bit[16] = 闰月大小
LUNAR_INFO = [
    0x04bd8,0x04ae0,0x0a570,0x054d5,0x0d260,0x0d950,0x16554,0x056a0,0x09ad0,0x055d2, # 1900-1909
    0x04ae0,0x0a5b6,0x0a4d0,0x0d250,0x1d255,0x0b540,0x0d6a0,0x0ada2,0x095b0,0x14977, # 1910-1919
    0x04970,0x0a4b0,0x0b4b5,0x06a50,0x06d40,0x1ab54,0x02b60,0x09570,0x052f2,0x04970, # 1920-1929
    0x06566,0x0d4a0,0x0ea50,0x06e95,0x05ad0,0x02b60,0x186e3,0x092e0,0x1c8d7,0x0c950, # 1930-1939
    0x0d4a0,0x1d8a6,0x0b550,0x056a0,0x1a5b4,0x025d0,0x092d0,0x0d2b2,0x0a950,0x0b557, # 1940-1949
    0x06ca0,0x0b550,0x15355,0x04da0,0x0a5b0,0x14573,0x052b0,0x0a9a8,0x0e950,0x06aa0, # 1950-1959
    0x0aea6,0x0ab50,0x04b60,0x0aae4,0x0a570,0x05260,0x0f263,0x0d950,0x05b57,0x056a0, # 1960-1969
    0x096d0,0x04dd5,0x04ad0,0x0a4d0,0x0d4d4,0x0d250,0x0d558,0x0b540,0x0b6a0,0x195a6, # 1970-1979
    0x095b0,0x049b0,0x0a974,0x0a4b0,0x0b27a,0x06a50,0x06d40,0x0af46,0x0ab60,0x09570, # 1980-1989
    0x04af5,0x04970,0x064b0,0x074a3,0x0ea50,0x06b58,0x055c0,0x0ab60,0x096d5,0x092e0, # 1990-1999
    0x0c960,0x0d954,0x0d4a0,0x0da50,0x07552,0x056a0,0x0abb7,0x025d0,0x092d0,0x0cab5, # 2000-2009
    0x0a950,0x0b4a0,0x0baa4,0x0ad50,0x055d9,0x04ba0,0x0a5b0,0x15176,0x052b0,0x0a930, # 2010-2019
    0x07954,0x06aa0,0x0ad50,0x05b52,0x04b60,0x0a6e6,0x0a4e0,0x0d260,0x0ea65,0x0d530, # 2020-2029
    0x05aa0,0x076a3,0x096d0,0x04afb,0x04ad0,0x0a4d0,0x1d0b6,0x0d250,0x0d520,0x0dd45, # 2030-2039
    0x0b5a0,0x056d0,0x055b2,0x049b0,0x0a577,0x0a4b0,0x0aa50,0x1b255,0x06d20,0x0ada0, # 2040-2049
    0x14b63,0x09370,0x049f8,0x04970,0x064b0,0x168a6,0x0ea50,0x06b20,0x1a6c4,0x0aae0, # 2050-2059
    0x0a2e0,0x0d2e3,0x0c960,0x0d557,0x0d4a0,0x0da50,0x05d55,0x056a0,0x0a6d0,0x055d4, # 2060-2069
    0x052d0,0x0a9b8,0x0a950,0x0b4a0,0x0b6a6,0x0ad50,0x055a0,0x0aba4,0x0a5b0,0x052b0, # 2070-2079
    0x0b273,0x06930,0x07337,0x06aa0,0x0ad50,0x14b55,0x04b60,0x0a570,0x054e4,0x0d160, # 2080-2089
    0x0e968,0x0d520,0x0daa0,0x16aa6,0x056d0,0x04ae0,0x0a9d4,0x0a2d0,0x0d150,0x0f252, # 2090-2099
    0x0d520,                                                                      # 2100
]
LUNAR_MONTH_DAYS = [29, 30]  # 小月29，大月30
# 农历月份名称（正月..十二月）
LUNAR_MONTH_NAMES = ["正月","二月","三月","四月","五月","六月","七月","八月","九月","十月","冬月","腊月"]
LUNAR_DAY_PREFIX = ["初","十","廿","三"]
LUNAR_DAY_NUM = ["一","二","三","四","五","六","七","八","九","十"]

def _lunar_year_days(year):
    days = 0
    info = LUNAR_INFO[year - 1900]
    for month in range(1, 13):
        # bit 15 = 正月，bit 4 = 腊月（即 bit (16-month)）
        days += 30 if (info >> (16 - month)) & 1 else 29
    # 闰月天数：bit 16 (0x10000) 1=30天, 0=29天
    leap = info & 0xf
    if leap:
        days += 30 if (info >> 16) & 1 else 29
    return days

def _lunar_month_days(year, month, is_leap=False):
    info = LUNAR_INFO[year - 1900]
    if is_leap:
        # 闰月天数：bit 16
        return 30 if (info >> 16) & 1 else 29
    # bit 15 = 正月，bit 4 = 腊月（即 bit (16-month)）
    return 30 if (info >> (16 - month)) & 1 else 29

def _leap_month(year):
    return LUNAR_INFO[year - 1900] & 0xf

def _leap_days(year):
    """返回该年闰月的天数，无闰月返回 0。"""
    info = LUNAR_INFO[year - 1900]
    if info & 0xf:
        return 30 if (info >> 16) & 1 else 29
    return 0

def solar_to_lunar(d: date):
    """公历 date 转农历，返回 (year, month, day, is_leap)。仅支持 1900-2100 公历年。"""
    if d.year < 1900 or d.year > 2100:
        return None
    base_date = date(1900, 1, 31)  # 1900-01-31 = 农历 1900 正月初一
    offset = (d - base_date).days
    if offset < 0:
        return None
    lunar_year = 1900
    # 先按整年累减，定位到所在农历年
    while lunar_year <= 2100 and offset >= 0:
        year_days = _lunar_year_days(lunar_year)
        if offset < year_days:
            break
        offset -= year_days
        lunar_year += 1
    if lunar_year > 2100:
        return None  # 超出 2100 年农历范围
    if offset < 0:
        # 极端边界：回退一年
        lunar_year -= 1
        offset += _lunar_year_days(lunar_year)
    leap = _leap_month(lunar_year)
    is_leap = False
    lunar_month = 1
    # 在年内按月累减
    while lunar_month <= 12 and offset >= 0:
        days = _lunar_month_days(lunar_year, lunar_month, False)
        if offset < days:
            break
        offset -= days
        if leap == lunar_month:
            leap_d = _leap_days(lunar_year)
            if offset < leap_d:
                is_leap = True
                break
            offset -= leap_d
        lunar_month += 1
    # 保护：不会出现 lunar_month > 12
    if lunar_month > 12:
        lunar_month = 12
    lunar_day = offset + 1
    return (lunar_year, lunar_month, lunar_day, is_leap)

def format_lunar_day(lunar):
    """格式化农历日为简短字符串：初一/十五/廿三 等显示月名；其余显示日名。"""
    if not lunar:
        return ""
    _, month, day, is_leap = lunar
    if day == 1:
        prefix = "闰" if is_leap else ""
        return prefix + LUNAR_MONTH_NAMES[month - 1]
    if day == 10:
        return "初十"
    if day == 20:
        return "二十"
    if day == 30:
        return "三十"
    prefix = LUNAR_DAY_PREFIX[day // 10]
    num = LUNAR_DAY_NUM[day % 10 - 1] if day % 10 != 0 else LUNAR_DAY_NUM[9]
    return prefix + num

def lunar_year_name(year):
    """农历年的生肖名。"""
    animals = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
    return animals[(year - 4) % 12]
