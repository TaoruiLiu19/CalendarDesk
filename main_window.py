import calendar as std_calendar
import time
from datetime import date, datetime

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout,
                               QPushButton, QLabel, QFrame, QSystemTrayIcon, QMenu,
                               QHBoxLayout, QVBoxLayout, QMessageBox, QSizePolicy,
                               QGraphicsDropShadowEffect, QDialog, QLineEdit,
                               QComboBox, QAbstractScrollArea)
from PySide6.QtGui import QFont, QAction, QMouseEvent, QPixmap, QPainter, QColor, QBrush, QPen, QIcon, QLinearGradient, QPalette
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, QEvent, QPropertyAnimation, QEasingCurve

from config import SETTING_FILE
from themes import THEMES, DEFAULT_THEME
from holiday import get_year_holidays, is_download_failed, clear_download_failed, HolidayDownloadThread
from festivals import get_day_extra_info
from memo import load_memos, get_effective_memos_for_date, save_day_memos, CATEGORY_COLORS, CATEGORY_LABELS, PRIORITY_LABELS
from dialogs import DateDetailDialog


class ModernAlertDialog(QDialog):
    """现代极简圆形提醒弹窗：纯圆主视觉 + 主题配色 + 半透明玻璃质感。"""

    def __init__(self, memo: dict, theme: dict, parent=None):
        super().__init__(parent)
        self._result_code = 0
        self.setWindowTitle("")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._memo = memo
        self._theme = theme
        self._build_ui()
        self._center_on_screen()
        self._fade_in()

    def _build_ui(self):
        m = self._memo
        t = m.get("time", "")
        text = m.get("text", "")
        remind_before = m.get("remind_before", 0)
        cat = m.get("category", "other")
        cat_color = CATEGORY_COLORS.get(cat, "#9e9e9e")
        cat_label = CATEGORY_LABELS.get(cat, "其他")
        pri = m.get("priority", "medium")
        repeat = m.get("repeat", "none")

        # 主题配色
        th = self._theme
        is_dark = th.get("is_dark", False)
        accent = th.get("accent", "#1976d2")
        text_color = th.get("text", "#333333")
        text_muted = th.get("text_muted", "#555555")
        btn_bg = th.get("btn_bg", "#f0f0f0")
        btn_hover = th.get("btn_hover", "#dddddd")

        # 卡片底色：从主题 window_bg 提取 RGB，统一 0.92 不透明度，与主题背景一致
        import re
        m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),", th.get("window_bg", ""))
        if m:
            card_bg = f"rgba({m.group(1)},{m.group(2)},{m.group(3)},0.92)"
        elif is_dark:
            card_bg = "rgba(45,45,48,0.92)"
        else:
            card_bg = "rgba(255,255,255,0.92)"
        border_color = "rgba(255,255,255,0.12)" if is_dark else "rgba(0,0,0,0.10)"
        ghost_text = text_muted
        ghost_hover_text = text_color

        # 圆形直径 420，外层留 36 边距给阴影
        D = 420
        self.setFixedSize(D + 72, D + 72)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(36, 36, 36, 36)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("alertCircle")
        card.setFixedSize(D, D)
        card.setStyleSheet(
            "QFrame#alertCircle{"
            f"background-color:{card_bg};"
            f"border:1px solid {border_color};"
            f"border-radius:{D // 2}px;}}")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(72)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(0, 0, 0, 45))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        # 圆形安全内容区：上下大量留白（圆形上下窄），左右中等留白
        layout = QVBoxLayout(card)
        layout.setSpacing(0)
        layout.setContentsMargins(90, 96, 90, 96)
        layout.setAlignment(Qt.AlignCenter)

        # 1. 顶部小圆点（分类色指示，仅作微妙标记）
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background:{cat_color};border:none;border-radius:4px;")
        dot_row = QHBoxLayout()
        dot_row.setAlignment(Qt.AlignCenter)
        dot_row.addWidget(dot)
        layout.addLayout(dot_row)

        layout.addSpacing(22)

        # 2. 时间（配角，小号，主题 accent 色）；无时间则用分类名
        if t:
            hero = QLabel(t)
            hero.setFont(QFont("Segoe UI", 15, QFont.Bold))
        else:
            hero = QLabel(cat_label)
            hero.setFont(QFont("Segoe UI", 13, QFont.Bold))
        hero.setStyleSheet(f"color:{accent};border:none;background:transparent;")
        hero.setAlignment(Qt.AlignCenter)
        layout.addWidget(hero)

        layout.addSpacing(14)

        # 3. 短分割线（主题 accent 色）
        line = QFrame()
        line.setFixedSize(36, 2)
        line.setStyleSheet(f"background:{accent};border:none;border-radius:1px;")
        line_row = QHBoxLayout()
        line_row.setAlignment(Qt.AlignCenter)
        line_row.addWidget(line)
        layout.addLayout(line_row)

        layout.addSpacing(16)

        # 4. 备忘内容（主角，大号加粗，主题正文色）
        if text:
            text_label = QLabel(text)
            text_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
            text_label.setStyleSheet(f"color:{text_color};border:none;background:transparent;")
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setWordWrap(True)
            text_label.setMaximumWidth(230)
            layout.addWidget(text_label)
        else:
            hint = QLabel("（无内容）")
            hint.setFont(QFont("Segoe UI", 12))
            hint.setStyleSheet(f"color:{text_muted};border:none;background:transparent;")
            hint.setAlignment(Qt.AlignCenter)
            layout.addWidget(hint)

        layout.addSpacing(12)

        # 5. 元信息一行小字（主题次要文字色）
        meta_parts = []
        if t:
            meta_parts.append(cat_label)
        pri_labels = {"high": "高优先级", "medium": "中优先级", "low": "低优先级"}
        if pri in pri_labels:
            meta_parts.append(pri_labels[pri])
        if remind_before > 0:
            meta_parts.append(f"提前{remind_before}分钟")
        if repeat != "none":
            from memo import REPEAT_OPTIONS
            meta_parts.append(REPEAT_OPTIONS.get(repeat, "重复"))
        if meta_parts:
            meta_label = QLabel(" · ".join(meta_parts))
            meta_label.setFont(QFont("Segoe UI", 8))
            meta_label.setStyleSheet(f"color:{text_muted};border:none;background:transparent;")
            meta_label.setAlignment(Qt.AlignCenter)
            meta_label.setMaximumWidth(210)
            layout.addWidget(meta_label)

        layout.addStretch(1)

        # 6. 按钮区：幽灵按钮（主题 btn_bg）+ 实心按钮（主题 accent）
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(10)

        btn_later = QPushButton("5分钟后再提醒")
        btn_later.setFixedSize(120, 32)
        btn_later.setCursor(Qt.PointingHandCursor)
        btn_later.setStyleSheet(
            f"QPushButton{{background:{btn_bg};color:{ghost_text};"
            "border:none;border-radius:16px;"
            "font-size:9pt;font-weight:bold;}"
            f"QPushButton:hover{{background:{btn_hover};color:{ghost_hover_text};}}")
        btn_later.clicked.connect(lambda: self._done(1))

        btn_ok = QPushButton("知道了")
        btn_ok.setFixedSize(78, 32)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(
            f"QPushButton{{background:{accent};color:white;border:none;border-radius:16px;"
            "font-size:9pt;font-weight:bold;}"
            f"QPushButton:hover{{background:{self._darken(accent)};}}")
        btn_ok.clicked.connect(lambda: self._done(0))

        btn_row.addWidget(btn_later)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.85) -> str:
        c = QColor(hex_color)
        h, s, v, a = c.getHsv()
        c.setHsv(h, s, max(0, int(v * factor)), a)
        return c.name()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2)

    def _fade_in(self):
        self.setWindowOpacity(0.0)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(280)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _done(self, code: int):
        self._result_code = code
        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out_anim.setDuration(180)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out_anim.finished.connect(lambda: QDialog.done(self, code))
        self._fade_out_anim.start()

    def done(self, code):
        if not hasattr(self, '_fade_out_anim') or not self._fade_out_anim.state():
            super().done(code)
        else:
            self._done(code)


class CalendarWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        self.topmost_flag = False
        self.drag_position = None
        self.RESIZE_MARGIN = 8
        self.resize_direction = 0
        self._force_quit = False
        self.current_theme = SETTING_FILE.value("theme", DEFAULT_THEME)
        if self.current_theme not in THEMES:
            self.current_theme = DEFAULT_THEME
        self.initUI()
        self.apply_theme()
        self.init_tray()
        geo = SETTING_FILE.value("geometry")
        if geo:
            self.restoreGeometry(geo)
            self._is_maximized = self.isMaximized()
            self.btn_max.setText("❐" if self._is_maximized else "▢")
            self.btn_max.setToolTip("还原" if self._is_maximized else "全屏")

        self.alert_timer = QTimer(self)
        self.alert_timer.setInterval(10000)  # 10 秒检查一次
        self.alert_timer.timeout.connect(self.check_memo_alert)
        self.alert_timer.start()
        self.triggered_alerts = set()  # 已提醒过的 key
        self._last_alert_date = None

    def check_memo_alert(self):
        now = datetime.now()
        today = now.date()
        today_str = today.strftime("%Y-%m-%d")
        now_min = now.hour * 60 + now.minute  # 当前分钟数

        # 日期切换时重置已触发集合 + 刷新托盘图标
        if today_str != self._last_alert_date:
            self.triggered_alerts.clear()
            self._last_alert_date = today_str
            if getattr(self, "tray", None) and QSystemTrayIcon.isSystemTrayAvailable():
                self.tray.setIcon(self._make_tray_icon())
            if getattr(self, "_rendered_date", None) != today:
                self._rendered_date = today
                self.render_calendar()

        # 获取当天有效备忘（含重复展开，排除 snooze）
        memo_list = get_effective_memos_for_date(today)

        for m in memo_list:
            if m.get("done", False):
                continue
            t = m.get("time", "")
            if not t:
                continue
            parts = t.split(":")
            memo_min = int(parts[0]) * 60 + int(parts[1])
            remind_before = m.get("remind_before", 0)
            alert_min = memo_min - remind_before
            # 使用备忘 id + time + remind_before 作为去重 key
            alert_key = f"{today_str}_{m.get('id', '')}_{t}_pre{remind_before}"

            # 精确匹配当前分钟，避免已过时间的提醒误触发（定时器每10秒检查，足够覆盖）
            if alert_min == now_min and alert_key not in self.triggered_alerts:
                self.triggered_alerts.add(alert_key)
                self._show_alert(m, alert_key)

    def _show_alert(self, memo: dict, alert_key: str):
        """弹出现代风格提醒对话框，支持稍后提醒。"""
        dlg = ModernAlertDialog(memo, THEMES.get(self.current_theme, THEMES[DEFAULT_THEME]), self)
        dlg.exec()
        if dlg.result() == 1:  # 稍后提醒（5 分钟）
            # 从已触发集合中移除，允许 Snooze 到期后再次提醒
            self.triggered_alerts.discard(alert_key)
            # 持久化 snooze：重复备忘按日期独立，非重复备忘用全局 snooze_until
            today_str = datetime.now().strftime("%Y-%m-%d")
            memos = load_memos()
            for k, memo_list in memos.items():
                for i, m in enumerate(memo_list):
                    if m.get("id") == memo.get("id"):
                        if m.get("repeat", "none") != "none":
                            # 重复备忘：写入 per-date snoozed_dates
                            m.setdefault("snoozed_dates", {})
                            m["snoozed_dates"][today_str] = time.time() + 5 * 60
                        else:
                            m["snooze_until"] = time.time() + 5 * 60
                        save_day_memos(date.fromisoformat(k), memo_list)
                        break

    def initUI(self):
        self.setWindowTitle("日历挂件")
        self.resize(660, 620)
        self.setMinimumSize(540, 500)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)
        self.layout_main = QGridLayout(self.central_widget)
        self.layout_main.setSpacing(4)
        self.layout_main.setContentsMargins(14,14,14,14)

        # ===== 第 0 行：主题按钮（左） + 窗口控制按钮（右） =====
        self.btn_theme = QPushButton("主题")
        self.btn_theme.setFixedSize(50,26)
        self.btn_theme.setToolTip("切换主题")

        self.btn_min = QPushButton("—")
        self.btn_min.setFixedSize(34,26)
        self.btn_min.setToolTip("最小化")
        self.btn_max = QPushButton("▢")
        self.btn_max.setFixedSize(34,26)
        self.btn_max.setToolTip("全屏/还原")
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(34,26)
        self.btn_close.setToolTip("关闭")
        self._is_maximized = False
        self._prev_geometry = None

        win_btn_layout = QHBoxLayout()
        win_btn_layout.setSpacing(2)
        win_btn_layout.setContentsMargins(0,0,0,0)
        win_btn_layout.addWidget(self.btn_theme)
        win_btn_layout.addStretch(1)
        win_btn_layout.addWidget(self.btn_min)
        win_btn_layout.addWidget(self.btn_max)
        win_btn_layout.addWidget(self.btn_close)
        win_container = QWidget()
        win_container.setLayout(win_btn_layout)
        self.layout_main.addWidget(win_container,0,0,1,7)

        # ===== 第 1 行：今天按钮 + 年月独立切换（居中） =====
        nav_btn_style = "QPushButton{border:none;border-radius:13px;background:#f0f0f0;font-size:13px;}QPushButton:hover{background:#dddddd;}"
        self.btn_prev_month = QPushButton("◀")
        self.btn_prev_month.setFixedSize(26,26)
        self.btn_prev_month.setStyleSheet(nav_btn_style)
        self.btn_prev_month.setToolTip("上个月")
        self.btn_next_month = QPushButton("▶")
        self.btn_next_month.setFixedSize(26,26)
        self.btn_next_month.setStyleSheet(nav_btn_style)
        self.btn_next_month.setToolTip("下个月")
        self.btn_prev_year = QPushButton("◀")
        self.btn_prev_year.setFixedSize(26,26)
        self.btn_prev_year.setStyleSheet(nav_btn_style)
        self.btn_prev_year.setToolTip("上一年")
        self.btn_next_year = QPushButton("▶")
        self.btn_next_year.setFixedSize(26,26)
        self.btn_next_year.setStyleSheet(nav_btn_style)
        self.btn_next_year.setToolTip("下一年")

        self.btn_today = QPushButton("今天")

        font_title = QFont("Segoe UI",13)
        font_title.setBold(True)
        self.label_year = QLabel("")
        self.label_year.setAlignment(Qt.AlignCenter)
        self.label_year.setFont(font_title)
        self.label_year.setMinimumWidth(70)
        self.label_month = QLabel("")
        self.label_month.setAlignment(Qt.AlignCenter)
        self.label_month.setFont(font_title)
        self.label_month.setMinimumWidth(45)

        # "今天"放左侧，年月切换组居中
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        nav_row.setContentsMargins(0,0,0,0)
        nav_row.addWidget(self.btn_today)
        nav_row.addStretch(1)
        nav_row.addWidget(self.btn_prev_year)
        nav_row.addWidget(self.label_year)
        nav_row.addWidget(self.btn_next_year)
        nav_row.addSpacing(12)
        nav_row.addWidget(self.btn_prev_month)
        nav_row.addWidget(self.label_month)
        nav_row.addWidget(self.btn_next_month)
        nav_row.addStretch(1)
        nav_container = QWidget()
        nav_container.setLayout(nav_row)
        self.layout_main.addWidget(nav_container,1,0,1,7)

        self.btn_prev_month.clicked.connect(self.go_prev_month)
        self.btn_next_month.clicked.connect(self.go_next_month)
        self.btn_prev_year.clicked.connect(self.go_prev_year)
        self.btn_next_year.clicked.connect(self.go_next_year)
        self.btn_today.clicked.connect(self.go_today)
        self.btn_theme.clicked.connect(self.show_theme_menu)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)
        self.btn_close.clicked.connect(self.close)

        self.week_labels = []
        week_names = ["日","一","二","三","四","五","六"]
        for idx,name in enumerate(week_names):
            lb = QLabel(name)
            lb.setAlignment(Qt.AlignCenter)
            lb.setMaximumHeight(26)
            lb.setFont(QFont("Segoe UI",10,QFont.Bold))
            self.layout_main.addWidget(lb,2,idx)
            self.week_labels.append(lb)

        self.day_labels = []
        for row in range(3,9):
            row_list = []
            for col in range(7):
                frame = QFrame()
                frame.setFrameShape(QFrame.StyledPanel)
                frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                lay_cell = QGridLayout(frame)
                lay_cell.setSpacing(0)
                lay_cell.setContentsMargins(4,4,4,4)
                lb_day = QLabel()
                lb_day.setAlignment(Qt.AlignTop|Qt.AlignHCenter)
                lb_day.setFont(QFont("Segoe UI",11,QFont.Bold))
                lb_day.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                lb_lunar = QLabel("")
                lb_lunar.setAlignment(Qt.AlignCenter)
                lb_lunar.setFont(QFont("Segoe UI",8))
                lb_lunar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                lb_dot = QLabel("")
                lb_dot.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)
                lb_dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                lay_cell.addWidget(lb_day,0,0)
                lay_cell.addWidget(lb_lunar,1,0)
                lay_cell.addWidget(lb_dot,2,0)
                self.layout_main.addWidget(frame,row,col)
                row_list.append((frame,lb_day,lb_lunar,lb_dot))
            self.day_labels.append(row_list)
        self.render_calendar()

        # 让标签对鼠标透明，使拖动事件能穿透到主窗口
        for lb in self.week_labels:
            lb.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.label_year.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.label_month.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # 安装全局事件过滤器，让子控件空白区域的鼠标事件能传递到主窗口进行拖动/缩放
        QApplication.instance().installEventFilter(self)

    def show_theme_menu(self):
        menu = QMenu(self)
        for name in THEMES.keys():
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(name == self.current_theme)
            act.triggered.connect(lambda checked, n=name: self.set_theme(n))
            menu.addAction(act)
        btn_pos = self.btn_theme.mapToGlobal(QPoint(0, self.btn_theme.height()))
        menu.exec(btn_pos)

    def set_theme(self, name):
        if name not in THEMES or name == self.current_theme:
            return
        self.current_theme = name
        SETTING_FILE.setValue("theme", name)
        self.apply_theme()

    def apply_theme(self):
        t = THEMES[self.current_theme]
        # 暗色主题用白色文字，亮色主题用黑色文字（窗口控制按钮）
        win_fg = "#ffffff" if t["is_dark"] else "#222222"
        # 主窗口背景
        self.central_widget.setStyleSheet(
            f"#centralWidget{{background-color:{t['window_bg']};border-radius:12px;}}")
        # 主题按钮：和窗口控制按钮同一行，风格一致，文字色随明暗
        self.btn_theme.setStyleSheet(
            f"QPushButton{{border:none;border-radius:4px;background:transparent;color:{win_fg};"
            f"font-size:12px;padding:4px 8px;}}"
            f"QPushButton:hover{{background:{t['win_btn_hover']};}}"
            f"QPushButton:pressed{{background:{t['win_btn_pressed']};}}")
        # 最小化 / 全屏按钮
        win_btn_style = (f"QPushButton{{border:none;border-radius:4px;background:transparent;color:{win_fg};"
                         f"font-size:13px;padding:4px 8px;}}"
                         f"QPushButton:hover{{background:{t['win_btn_hover']};}}"
                         f"QPushButton:pressed{{background:{t['win_btn_pressed']};}}")
        for btn in (self.btn_min, self.btn_max):
            btn.setStyleSheet(win_btn_style)
        # 关闭按钮：常态用主题明暗文字色，hover/pressed 保持红色 + 白字（通用约定）
        self.btn_close.setStyleSheet(
            f"QPushButton{{border:none;border-radius:4px;background:transparent;color:{win_fg};"
            f"font-size:13px;padding:4px 8px;}}"
            "QPushButton:hover{background:#e53935;color:white;}"
            "QPushButton:pressed{background:#c62828;color:white;}")
        # 导航切换按钮
        nav_btn_style = (f"QPushButton{{border:none;border-radius:13px;background:{t['btn_bg']};color:{t['text']};font-size:13px;}}"
                         f"QPushButton:hover{{background:{t['btn_hover']};}}")
        for btn in (self.btn_prev_month, self.btn_next_month, self.btn_prev_year, self.btn_next_year):
            btn.setStyleSheet(nav_btn_style)
        # "今天"按钮
        self.btn_today.setStyleSheet(
            f"QPushButton{{background:{t['accent_bg']};color:{t['accent']};border:none;"
            f"border-radius:5px;padding:4px 10px;font-size:10pt;}}"
            f"QPushButton:hover{{background:{t['accent_hover']};}}")
        # 年月标签
        year_month_ss = f"color:{t['text']};"
        self.label_year.setStyleSheet(year_month_ss)
        self.label_month.setStyleSheet(year_month_ss)
        # 星期表头
        week_ss = f"color:{t['text_muted']};"
        for lb in self.week_labels:
            lb.setStyleSheet(week_ss)
        # 重新渲染日历格子（应用单元格颜色）
        self.render_calendar()

    def _on_holiday_downloaded(self, year: int):
        """后台下载完成回调：仅当当前显示的年份匹配时才重绘。"""
        if year == self.current_year:
            self.render_calendar()

    def _on_holiday_failed(self, year: int):
        """后台下载失败回调：托盘气泡提示。"""
        if getattr(self, "tray", None) and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.showMessage("日历挂件", f"{year}年节假日数据下载失败，将使用周末判断", self.tray.icon(), 3000)

    def _apply_today_glass(self, frame: QFrame, has_memo: bool):
        """对今日单元格应用磨砂玻璃质感。
        - 单一半透明圆角矩形背景（无边框线条）
        - 子标签全部 background:transparent，确保只有一个大圆角矩形
        """
        t = THEMES[self.current_theme]
        glass_bg = t["today_glass_bg"]
        # frame 样式：单一半透明底色 + 圆角，无边框
        bg = (f"QFrame {{"
              f"background-color:{glass_bg};"
              f"border:none;"
              f"border-radius:8px;}}")
        frame.setStyleSheet(bg)
        # 强制子标签透明背景，防止 Qt 给有 stylesheet 的 QLabel 绘制默认底色
        for child in frame.findChildren(QLabel):
            child.setStyleSheet(child.styleSheet() + ";background:transparent;")
        # 移除旧特效（QGraphicsDropShadowEffect 会导致亮色主题下文字模糊）
        old_eff = frame.graphicsEffect()
        if old_eff is not None:
            old_eff.setParent(None)
            frame.setGraphicsEffect(None)

    def render_calendar(self):
        t = THEMES[self.current_theme]
        self.label_year.setText(f"{self.current_year}年")
        self.label_month.setText(f"{self.current_month}月")
        # 尝试从缓存读取当年节假日；若缓存缺失则启动后台下载线程（不阻塞 UI），完成后重绘
        cached = get_year_holidays(self.current_year, allow_download=False)
        if cached is None:
            if is_download_failed(self.current_year):
                # 用户切换到此年，清除失败标记允许重试一次
                clear_download_failed(self.current_year)
            if not is_download_failed(self.current_year):
                # 启动后台下载（仅当该年无缓存且未失败过）
                if not getattr(self, "_download_threads", None):
                    self._download_threads = {}
                # 同一年同时只有一个下载线程
                if self.current_year not in self._download_threads or not self._download_threads[self.current_year].isRunning():
                    dl_thread = HolidayDownloadThread(self.current_year)
                    dl_thread.download_done.connect(self._on_holiday_downloaded)
                    dl_thread.download_failed.connect(self._on_holiday_failed)
                    self._download_threads[self.current_year] = dl_thread
                    dl_thread.start()
        cal = std_calendar.Calendar(firstweekday=6).monthdayscalendar(self.current_year,self.current_month)
        today = date.today()
        memos = load_memos()
        for r in range(6):
            for c in range(7):
                frame,lb_day,lb_lunar,lb_dot = self.day_labels[r][c]
                lb_day.setText("")
                lb_lunar.setText("")
                lb_dot.setText("")
                lb_day.setStyleSheet(f"color:{t['text']};background:transparent;")
                lb_lunar.setStyleSheet(f"color:{t['text_muted']};background:transparent;")
                frame.setStyleSheet(f"QFrame{{background:transparent;border-radius:5px;}}")
                frame.setToolTip("")
                frame.mousePressEvent = lambda event: None

        for row_idx,week in enumerate(cal):
            for col_idx,day in enumerate(week):
                frame,lb_day,lb_lunar,lb_dot = self.day_labels[row_idx][col_idx]
                if day == 0:
                    continue
                lb_day.setText(str(day))
                lb_day.setStyleSheet(f"color:{t['text']};background:transparent;")
                d = date(self.current_year,self.current_month,day)
                frame.mousePressEvent = lambda event,dt=d:self.show_date_info(dt)
                key = d.strftime("%Y-%m-%d")
                memo_list = get_effective_memos_for_date(d)  # 含重复展开

                # 农历 / 节假日信息
                extra_text, is_rest_day, is_holiday_name, is_workday_adjust = get_day_extra_info(d)
                if is_workday_adjust:
                    # 调休上班日："班"字用显眼红色加粗，后面的农历/节日保留 muted 色
                    if extra_text.startswith("班·"):
                        ban_part = extra_text[:len("班")]
                        rest_part = extra_text[len("班"):]
                        lb_lunar.setText(
                            f'<span style="color:{t["weekend"]};font-weight:bold;">{ban_part}</span>'
                            f'<span style="color:{t["text_muted"]};">{rest_part}</span>')
                    else:  # 纯 "班"
                        lb_lunar.setText(
                            f'<span style="color:{t["weekend"]};font-weight:bold;">{extra_text}</span>')
                    lb_lunar.setStyleSheet("background:transparent;")
                else:
                    lb_lunar.setText(extra_text)
                    if is_rest_day:
                        # 休息日：节日名加粗红，普通周末农历用红色不加粗
                        if is_holiday_name:
                            lb_lunar.setStyleSheet(f"color:{t['weekend']};font-weight:bold;background:transparent;")
                        else:
                            lb_lunar.setStyleSheet(f"color:{t['weekend']};background:transparent;")
                    else:
                        # 普通工作日
                        if is_holiday_name:
                            lb_lunar.setStyleSheet(f"color:{t['accent']};font-weight:bold;background:transparent;")
                        else:
                            lb_lunar.setStyleSheet(f"color:{t['text_muted']};background:transparent;")

                # 网格预览：按分类着色的色块条 + 高优先级感叹号
                # 收集分类色（去重，最多3个）
                cat_colors = []
                has_high = False
                for m in memo_list:
                    cat = m.get("category", "other")
                    c = CATEGORY_COLORS.get(cat, "#9e9e9e")
                    if c not in cat_colors:
                        cat_colors.append(c)
                    if m.get("priority") == "high" and not m.get("done", False):
                        has_high = True
                dot_html = ""
                for c in cat_colors[:3]:
                    dot_html += f'<span style="color:{c};font-size:8pt;">■</span>'
                if has_high:
                    dot_html = f'<span style="color:#e53935;font-size:9pt;font-weight:bold;">!</span>' + dot_html
                lb_dot.setText(dot_html)

                if memo_list:
                    tip_lines = [f"{d.year}年{d.month}月{d.day}日 备忘录："]
                    for m in memo_list:
                        ti = m.get("time","")
                        txt = m.get("text","")
                        done_mark = "✅" if m.get("done") else ""
                        if ti:
                            tip_lines.append(f"⏰{ti} {done_mark}{txt}")
                        else:
                            tip_lines.append(f"📄 {done_mark}{txt}")
                    frame.setToolTip("\n".join(tip_lines))
                    if d == today:
                        self._apply_today_glass(frame, True)
                    else:
                        frame.setStyleSheet(f"QFrame{{background-color:{t['cell_memo_bg']};border-radius:5px;}}")
                else:
                    lb_dot.setText("")
                    if d == today:
                        self._apply_today_glass(frame, False)

                # 日期数字颜色：今日用浮雕文字色（高对比度），其他日子按休息日/工作日着色
                if d == today:
                    lb_day.setStyleSheet(
                        f"color:{t['today_glass_text']};font-weight:bold;font-size:12pt;background:transparent;")
                elif is_rest_day:
                    lb_day.setStyleSheet(f"color:{t['weekend']};background:transparent;")
        self._rendered_date = today

    def show_date_info(self,d:date):
        dlg = DateDetailDialog(d, THEMES.get(self.current_theme, THEMES[DEFAULT_THEME]), self)
        dlg.exec()
        self.render_calendar()

    def go_prev_month(self):
        if self.current_month ==1:
            if self.current_year <= 1900:
                return
            self.current_month=12
            self.current_year -=1
        else:
            self.current_month -=1
        self.render_calendar()

    def go_next_month(self):
        if self.current_month ==12:
            if self.current_year >= 2100:
                return
            self.current_month=1
            self.current_year +=1
        else:
            self.current_month +=1
        self.render_calendar()

    def go_prev_year(self):
        if self.current_year <= 1900:
            return
        self.current_year -=1
        self.render_calendar()

    def go_next_year(self):
        if self.current_year >= 2100:
            return
        self.current_year +=1
        self.render_calendar()

    def go_today(self):
        t = date.today()
        self.current_year = t.year
        self.current_month = t.month
        self.render_calendar()

    def _make_tray_icon(self):
        size = 64
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        # 日历卡纸张
        base = QColor("#ffffff")
        p.setBrush(QBrush(base))
        p.setPen(QPen(QColor("#2196f3"), 2))
        p.drawRoundedRect(2, 8, size-4, size-10, 6, 6)
        # 顶部红色横条（撕页效果）
        p.setBrush(QBrush(QColor("#e53935")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(2, 8, size-4, 14, 6, 6)
        # 日期数字
        today_num = str(datetime.now().day)
        font = p.font()
        font.setBold(True)
        font.setPixelSize(30)
        p.setFont(font)
        p.setPen(QPen(QColor("#333333")))
        p.drawText(pm.rect(), Qt.AlignCenter, today_num)
        p.end()
        return QIcon(pm)

    def _show_restore(self):
        if self.isMinimized():
            self.showNormal()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def _toggle_visible(self):
        if self.isMinimized() or not self.isVisible():
            self._show_restore()
        else:
            self.hide()

    def init_tray(self):
        icon = self._make_tray_icon()
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(icon)
        self.tray.setToolTip("日历挂件")
        tray_menu = QMenu()
        act_show = QAction("显示/隐藏窗口", self)
        act_show.triggered.connect(self._toggle_visible)
        act_top = QAction("切换窗口置顶", self)
        act_top.triggered.connect(self.toggle_topmost)
        act_close_tray = QAction("关闭时最小化到托盘", self)
        act_close_tray.setCheckable(True)
        act_close_tray.setChecked(SETTING_FILE.value("close_to_tray", True, type=bool))
        act_close_tray.triggered.connect(self.toggle_close_to_tray)
        act_exit = QAction("完全退出程序", self)
        act_exit.triggered.connect(self.quit_app)
        tray_menu.addAction(act_show)
        tray_menu.addAction(act_top)
        tray_menu.addAction(act_close_tray)
        tray_menu.addSeparator()
        tray_menu.addAction(act_exit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.on_tray_click)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            print("警告：系统托盘不可用，关闭窗口后将无法通过托盘恢复")

    def on_tray_click(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick, QSystemTrayIcon.MiddleClick):
            self._toggle_visible()

    def toggle_topmost(self):
        self.topmost_flag = not self.topmost_flag
        self.setWindowFlag(Qt.WindowStaysOnTopHint,self.topmost_flag)
        self.show()

    def toggle_close_to_tray(self, checked):
        SETTING_FILE.setValue("close_to_tray", checked)

    def toggle_maximize(self):
        if self._is_maximized:
            self._is_maximized = False
            self.btn_max.setText("▢")
            self.btn_max.setToolTip("全屏")
            if self._prev_geometry:
                self.restoreGeometry(self._prev_geometry)
        else:
            self._prev_geometry = self.saveGeometry()
            self._is_maximized = True
            self.btn_max.setText("❐")
            self.btn_max.setToolTip("还原")
            self.showMaximized()

    def handle_new_connection(self):
        """处理单实例唤醒连接：收到第二实例的信号后显示窗口。"""
        sock = self._single_server.nextPendingConnection()
        if sock:
            sock.readyRead.connect(lambda s=sock: self._handle_single_cmd(s))
            sock.disconnected.connect(sock.deleteLater)

    def _handle_single_cmd(self, sock):
        data = bytes(sock.readAll())
        if b"show" in data:
            self._show_restore()
        sock.disconnectFromServer()

    def quit_app(self):
        """真正退出程序：设置强制退出标志后触发关闭事件，由 closeEvent 统一清理。"""
        self._force_quit = True
        self.close()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                # 最小化：保留任务栏 + 托盘同时可见，用户两边都能点回来
                if getattr(self, "tray", None) and QSystemTrayIcon.isSystemTrayAvailable():
                    self.tray.showMessage("日历挂件", "已最小化，点击托盘图标恢复", self.tray.icon(), 2000)
        super().changeEvent(event)

    def closeEvent(self,event):
        # 最大化状态下不保存 geometry，防止下次启动用最大化尺寸还原
        if not self._is_maximized:
            SETTING_FILE.setValue("geometry", self.saveGeometry())
        tray_ok = getattr(self, "tray", None) and QSystemTrayIcon.isSystemTrayAvailable()
        close_to_tray = SETTING_FILE.value("close_to_tray", True, type=bool)
        if self._force_quit or not tray_ok or not close_to_tray:
            # 真正退出：停止定时器、销毁托盘图标、结束进程
            if getattr(self, "alert_timer", None):
                self.alert_timer.stop()
            if getattr(self, "tray", None):
                self.tray.hide()
            event.accept()
            QApplication.quit()
        else:
            # 托盘可用且允许驻留：隐藏到后台
            event.ignore()
            self.hide()
            if not SETTING_FILE.value("close_to_tray_tip_shown", False, type=bool):
                self.tray.showMessage("日历挂件", "程序已最小化到托盘，双击托盘图标可重新打开窗口", self.tray.icon(), 3000)
                SETTING_FILE.setValue("close_to_tray_tip_shown", True)
            else:
                self.tray.showMessage("日历挂件", "已驻留后台，点击托盘图标恢复", self.tray.icon(), 2000)

    def eventFilter(self, obj, event):
        """全局事件过滤器：将子控件上的鼠标事件转发给主窗口，以支持无边框窗口的拖动和边缘缩放。
        白名单策略：仅转发非交互控件的鼠标事件，避免误拖动编辑框/下拉框/滚动区域。"""
        if not isinstance(obj, QWidget) or not self.isAncestorOf(obj):
            return super().eventFilter(obj, event)
        # 不转发交互控件的事件（编辑框、下拉框、滚动区域、按钮、日期格子）
        if isinstance(obj, (QPushButton, QFrame, QLineEdit, QComboBox, QAbstractScrollArea)):
            return super().eventFilter(obj, event)
        if event.type() == QEvent.MouseButtonPress:
            self.mousePressEvent(event)
        elif event.type() == QEvent.MouseMove:
            self.mouseMoveEvent(event)
        elif event.type() == QEvent.MouseButtonRelease:
            self.mouseReleaseEvent(event)
        return super().eventFilter(obj, event)

    def get_resize_edge(self, pos):
        rect = self.rect()
        edge = 0
        left = pos.x() <= self.RESIZE_MARGIN
        right = pos.x() >= rect.width() - self.RESIZE_MARGIN
        top = pos.y() <= self.RESIZE_MARGIN
        bottom = pos.y() >= rect.height() - self.RESIZE_MARGIN
        if left:
            edge |= 1
        if right:
            edge |= 2
        if top:
            edge |=4
        if bottom:
            edge |=8
        return edge

    def set_cursor_by_edge(self,edge):
        if (edge &1 and edge &4) or (edge &2 and edge &8):
            self.setCursor(Qt.SizeFDiagCursor)
        elif (edge &1 and edge &8) or (edge &2 and edge &4):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edge &1 or edge &2:
            self.setCursor(Qt.SizeHorCursor)
        elif edge &4 or edge &8:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self,event:QMouseEvent):
        pos = event.pos()
        self.resize_direction = self.get_resize_edge(pos)
        if self.resize_direction !=0:
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_start_geo = self.frameGeometry()
            event.accept()
        elif event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self,event:QMouseEvent):
        pos = event.pos()
        if self.resize_direction !=0:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            new_geo = geo
            if self.resize_direction &1:
                new_geo.setLeft(geo.left()+delta.x())
            if self.resize_direction &2:
                new_geo.setRight(geo.right()+delta.x())
            if self.resize_direction &4:
                new_geo.setTop(geo.top()+delta.y())
            if self.resize_direction &8:
                new_geo.setBottom(geo.bottom()+delta.y())
            if new_geo.width() >= self.minimumWidth() and new_geo.height()>=self.minimumHeight():
                self.setGeometry(new_geo)
            event.accept()
        elif event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint()-self.drag_position)
            event.accept()
        else:
            edge = self.get_resize_edge(pos)
            self.set_cursor_by_edge(edge)

    def mouseReleaseEvent(self,event):
        self.resize_direction = 0
        self.drag_position = None
        self.setCursor(Qt.ArrowCursor)
