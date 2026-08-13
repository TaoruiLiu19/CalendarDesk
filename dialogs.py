import re
import uuid
from datetime import date

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QListWidgetItem, QLineEdit,
                               QFrame, QTimeEdit, QComboBox, QCheckBox, QScrollArea,
                               QSizePolicy, QGridLayout, QWidget)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTime

from memo import (get_day_memos, save_day_memos, get_sorted_memos,
                  get_effective_memos_for_date,
                  CATEGORY_COLORS, CATEGORY_LABELS, PRIORITY_LABELS, REPEAT_OPTIONS)
from lunar import solar_to_lunar, format_lunar_day, lunar_year_name, LUNAR_MONTH_NAMES
from festivals import get_day_extra_info


class MemoCardWidget(QFrame):
    """单条备忘录的卡片控件，支持就地编辑。"""

    def __init__(self, memo_data: dict, parent=None, on_priority_changed=None):
        super().__init__(parent)
        self.memo = memo_data
        self._on_priority_changed = on_priority_changed
        self.setObjectName("memoCard")
        self._build_ui()

    def _build_ui(self):
        cat = self.memo.get("category", "other")
        cat_color = CATEGORY_COLORS.get(cat, "#9e9e9e")

        # 左侧颜色条
        self.color_bar = QFrame()
        self.color_bar.setFixedWidth(4)
        self.color_bar.setStyleSheet(f"background-color:{cat_color};border-radius:2px;")

        # 完成勾选框
        self.chk_done = QCheckBox()
        self.chk_done.setChecked(self.memo.get("done", False))
        self.chk_done.stateChanged.connect(self._on_done_changed)

        # 时间选择
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setMinimumWidth(90)
        t = self.memo.get("time", "")
        if t and ":" in t:
            parts = t.split(":")
            self.time_edit.setTime(QTime(int(parts[0]), int(parts[1])))
        else:
            self.time_edit.setSpecialValueText("无定时")
            self.time_edit.setTime(QTime(0, 0))
        self.time_edit.timeChanged.connect(self._on_time_changed)

        # 无定时勾选
        self.chk_no_time = QCheckBox("无定时")
        self.chk_no_time.setChecked(not t)
        self.chk_no_time.toggled.connect(self._on_no_time_toggled)
        if not t:
            self.time_edit.setEnabled(False)

        # 内容输入
        self.text_input = QLineEdit(self.memo.get("text", ""))
        self.text_input.setPlaceholderText("备忘内容…")
        self.text_input.textChanged.connect(self._on_text_changed)

        # 分类下拉
        self.combo_cat = QComboBox()
        self.combo_cat.setMinimumWidth(70)
        for k, v in CATEGORY_LABELS.items():
            self.combo_cat.addItem(v, k)
        self.combo_cat.setCurrentIndex(self.combo_cat.findData(cat))
        self.combo_cat.currentIndexChanged.connect(self._on_cat_changed)

        # 优先级下拉
        self.combo_pri = QComboBox()
        self.combo_pri.setMinimumWidth(60)
        for k, v in PRIORITY_LABELS.items():
            self.combo_pri.addItem(v, k)
        self.combo_pri.setCurrentIndex(self.combo_pri.findData(self.memo.get("priority", "medium")))
        self.combo_pri.currentIndexChanged.connect(self._on_pri_changed)

        # 提前提醒
        self.combo_remind = QComboBox()
        self.combo_remind.setMinimumWidth(80)
        for mins, label in [(0, "准点提醒"), (5, "提前5分"), (10, "提前10分"), (15, "提前15分"), (30, "提前30分"), (60, "提前1时")]:
            self.combo_remind.addItem(label, mins)
        self.combo_remind.setCurrentIndex(self.combo_remind.findData(self.memo.get("remind_before", 0)))
        self.combo_remind.currentIndexChanged.connect(self._on_remind_changed)

        # 重复
        self.combo_repeat = QComboBox()
        self.combo_repeat.setMinimumWidth(70)
        for k, v in REPEAT_OPTIONS.items():
            self.combo_repeat.addItem(v, k)
        self.combo_repeat.setCurrentIndex(self.combo_repeat.findData(self.memo.get("repeat", "none")))
        self.combo_repeat.currentIndexChanged.connect(self._on_repeat_changed)

        # 删除按钮
        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(28, 28)
        self.btn_del.setStyleSheet("QPushButton{border:none;border-radius:4px;background:transparent;color:#e53935;font-size:14px;}QPushButton:hover{background:#ffebee;}")

        # 第一行：完成勾选 + 内容输入(弹性) + 删除
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(self.chk_done)
        row1.addWidget(self.text_input, 1)
        row1.addWidget(self.btn_del)

        # 第二行：时间 + 无定时 + 分类 + 优先级 + 提前提醒 + 重复
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.addWidget(self.time_edit)
        row2.addWidget(self.chk_no_time)
        row2.addWidget(self.combo_cat)
        row2.addWidget(self.combo_pri)
        row2.addWidget(self.combo_remind)
        row2.addWidget(self.combo_repeat)

        rows = QVBoxLayout()
        rows.setSpacing(6)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.addLayout(row1)
        rows.addLayout(row2)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.addWidget(self.color_bar)
        main_layout.addLayout(rows, 1)

        self._apply_card_style()

    def _apply_card_style(self):
        cat = self.memo.get("category", "other")
        cat_color = CATEGORY_COLORS.get(cat, "#9e9e9e")
        self.color_bar.setStyleSheet(f"background-color:{cat_color};border-radius:2px;")
        self.setStyleSheet(
            "QFrame#memoCard{background-color:rgba(250,250,250,0.8);"
            "border:1px solid rgba(0,0,0,0.06);border-radius:6px;}"
            "QFrame#memoCard:hover{border:1px solid rgba(0,0,0,0.12);}")

    def _on_done_changed(self, state):
        self.memo["done"] = bool(state)
        font = self.text_input.font()
        font.setStrikeOut(self.memo["done"])
        self.text_input.setFont(font)

    def _on_time_changed(self, qt_time):
        if not self.chk_no_time.isChecked():
            self.memo["time"] = qt_time.toString("HH:mm")

    def _on_no_time_toggled(self, checked):
        self.time_edit.setEnabled(not checked)
        if checked:
            self.memo["time"] = ""
        else:
            self.memo["time"] = self.time_edit.time().toString("HH:mm")

    def _on_text_changed(self, text):
        self.memo["text"] = text

    def _on_cat_changed(self, idx):
        self.memo["category"] = self.combo_cat.currentData()
        self._apply_card_style()

    def _on_pri_changed(self, idx):
        self.memo["priority"] = self.combo_pri.currentData()
        if self._on_priority_changed:
            self._on_priority_changed()

    def _on_remind_changed(self, idx):
        self.memo["remind_before"] = self.combo_remind.currentData()

    def _on_repeat_changed(self, idx):
        self.memo["repeat"] = self.combo_repeat.currentData()


class MemoEditDialog(QDialog):
    """卡片化备忘录编辑对话框。"""

    def __init__(self, d: date, theme: dict, parent=None):
        super().__init__(parent)
        self.target_date = d
        self.setWindowTitle(f"备忘录编辑 {d.year}-{d.month:02d}-{d.day:02d}")
        self.resize(860, 520)
        self.memo_list = [dict(m) for m in get_day_memos(d)]
        self._theme = theme

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)

        # 顶部日期信息
        top_label = QLabel(f"📅 {d.year}年{d.month}月{d.day}日 的备忘录")
        top_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(top_label)

        # 滚动区域 + 卡片容器
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(6)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll, 1)

        self._refresh_cards()

        # 底部按钮（主题配色）
        accent = theme.get("accent", "#1976d2")
        accent_bg = theme.get("accent_bg", "#e3f2fd")
        accent_hover = theme.get("accent_hover", "#bbdefb")
        btn_color = theme.get("btn_bg", "#f0f0f0")
        btn_hover = theme.get("btn_hover", "#dddddd")
        text_color = theme.get("text", "#333333")
        text_muted = theme.get("text_muted", "#555555")

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 添加备忘")
        btn_add.setStyleSheet(f"QPushButton{{background:{accent_bg};color:{accent};border:none;border-radius:6px;padding:8px 16px;font-size:11pt;}}QPushButton:hover{{background:{accent_hover};}}")
        btn_save = QPushButton("💾 保存关闭")
        btn_save.setStyleSheet(f"QPushButton{{background:{accent};color:white;border:none;border-radius:6px;padding:8px 16px;font-size:11pt;}}QPushButton:hover{{background:{self._darken(accent)};}}")
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet(f"QPushButton{{background:{btn_color};color:{text_muted};border:none;border-radius:6px;padding:8px 16px;font-size:11pt;}}QPushButton:hover{{background:{btn_hover};color:{text_color};}}")
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        btn_add.clicked.connect(self.add_card)
        btn_save.clicked.connect(self.do_save)
        btn_cancel.clicked.connect(self.reject)

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.85) -> str:
        from PySide6.QtGui import QColor
        c = QColor(hex_color)
        h, s, v, a = c.getHsv()
        c.setHsv(h, s, max(0, int(v * factor)), a)
        return c.name()

    def _refresh_cards(self):
        # 清除旧卡片（保留 stretch）
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        # 按优先级排序后重建
        for m in get_sorted_memos(self.memo_list):
            card = MemoCardWidget(m, self, on_priority_changed=self._refresh_cards)
            card.btn_del.clicked.connect(lambda checked, c=card: self.del_card(c))
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def add_card(self):
        new_memo = {
            "id": str(uuid.uuid4())[:8],
            "time": "",
            "text": "",
            "category": "other",
            "priority": "medium",
            "done": False,
            "remind_before": 0,
            "repeat": "none",
        }
        self.memo_list.append(new_memo)
        card = MemoCardWidget(new_memo, self, on_priority_changed=self._refresh_cards)
        card.btn_del.clicked.connect(lambda checked, c=card: self.del_card(c))
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def del_card(self, card: MemoCardWidget):
        if card.memo in self.memo_list:
            self.memo_list.remove(card.memo)
        card.setParent(None)
        card.deleteLater()

    def do_save(self):
        # 保存所有备忘（允许仅含时间的提醒，不强制要求文本）
        save_day_memos(self.target_date, self.memo_list)
        self.accept()


class DateDetailDialog(QDialog):
    def __init__(self, d: date, theme: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日期详情")
        self.resize(500, 460)
        self.target_date = d
        self._theme = theme

        accent = theme.get("accent", "#1976d2")
        accent_bg = theme.get("accent_bg", "#e3f2fd")
        accent_hover = theme.get("accent_hover", "#bbdefb")
        btn_color = theme.get("btn_bg", "#f0f0f0")
        btn_hover = theme.get("btn_hover", "#dddddd")
        text_color = theme.get("text", "#333333")
        text_muted = theme.get("text_muted", "#555555")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        # 日期标题
        title_label = QLabel(f"📅 {d.year}年{d.month}月{d.day}日")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title_label)

        # 基本信息
        info_lines = []
        wd_text = ["周一","周二","周三","周四","周五","周六","周日"][d.weekday()]
        info_lines.append(f"星期：{wd_text}")
        lunar = solar_to_lunar(d)
        if lunar:
            ly, lm, ld, is_leap = lunar
            lunar_day_str = format_lunar_day(lunar)
            if ld == 1:
                full_lunar = f"农历：{lunar_year_name(ly)}年 {lunar_day_str}"
            else:
                leap_prefix = "闰" if is_leap else ""
                full_lunar = f"农历：{lunar_year_name(ly)}年 {leap_prefix}{LUNAR_MONTH_NAMES[lm-1]}{lunar_day_str}"
            info_lines.append(full_lunar)
        extra_text, is_rest_day, is_holiday_name, is_workday_adjust = get_day_extra_info(d)
        if is_holiday_name:
            tag = "🎉 法定假日" if is_rest_day else "节日"
            info_lines.append(f"{tag}：{extra_text}")
        elif is_rest_day:
            info_lines.append("休息日")
        if is_workday_adjust:
            info_lines.append("⚠️ 调休上班日")

        info_label = QLabel("\n".join(info_lines))
        info_label.setFont(QFont("Segoe UI", 10))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 分割线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:rgba(128,128,128,0.3);")
        layout.addWidget(sep)

        # 备忘录区域（含重复展开，与主日历格子一致）
        memo_list = get_effective_memos_for_date(d)
        memo_header = QHBoxLayout()
        memo_title = QLabel(f"📝 备忘录（{len(memo_list)} 条）" if memo_list else "📝 备忘录（暂无）")
        memo_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        memo_header.addWidget(memo_title)
        memo_header.addStretch(1)
        btn_memo = QPushButton("编辑备忘录")
        btn_memo.setStyleSheet(f"QPushButton{{background:{accent_bg};color:{accent};border:none;border-radius:5px;padding:5px 12px;}}QPushButton:hover{{background:{accent_hover};}}")
        memo_header.addWidget(btn_memo)
        layout.addLayout(memo_header)

        if memo_list:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout(scroll_widget)
            scroll_layout.setSpacing(6)
            scroll_layout.setContentsMargins(0, 0, 0, 0)
            scroll_layout.addStretch(1)
            for m in memo_list:
                card = self._build_readonly_card(m)
                scroll_layout.insertWidget(scroll_layout.count() - 1, card)
            scroll.setWidget(scroll_widget)
            layout.addWidget(scroll, 1)
        else:
            empty_label = QLabel("暂无备忘录，点击「编辑备忘录」添加")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet(f"color:{text_muted};font-size:11pt;padding:20px;")
            layout.addWidget(empty_label, 1)

        # 底部确定
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet(f"QPushButton{{background:{btn_color};color:{text_muted};border:none;border-radius:6px;padding:8px 24px;font-size:11pt;}}QPushButton:hover{{background:{btn_hover};color:{text_color};}}")
        layout.addWidget(btn_ok, 0, Qt.AlignRight)
        btn_ok.clicked.connect(self.accept)
        btn_memo.clicked.connect(self.open_memo_edit)

    def _build_readonly_card(self, m: dict) -> QFrame:
        """构建只读备忘卡片（日期详情中展示用）。"""
        cat = m.get("category", "other")
        cat_color = CATEGORY_COLORS.get(cat, "#9e9e9e")
        pri = m.get("priority", "medium")
        done = m.get("done", False)
        t = m.get("time", "")
        text = m.get("text", "")
        repeat = m.get("repeat", "none")

        card = QFrame()
        card.setObjectName("readonlyCard")
        card.setStyleSheet(
            "QFrame#readonlyCard{background-color:rgba(250,250,250,0.8);"
            "border:1px solid rgba(0,0,0,0.06);border-radius:6px;}")

        # 左侧颜色条
        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background-color:{cat_color};border-radius:2px;")

        # 时间徽章
        time_text = f"⏰ {t}" if t else "📄"
        if repeat != "none":
            time_text += f" 🔁{REPEAT_OPTIONS.get(repeat, '')}"
        time_label = QLabel(time_text)
        time_label.setFixedWidth(120)
        time_label.setStyleSheet(f"color:{cat_color};font-weight:bold;font-size:9pt;")

        # 内容
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setFont(QFont("Segoe UI", 10))
        if done:
            f = text_label.font()
            f.setStrikeOut(True)
            text_label.setFont(f)
            text_label.setStyleSheet("color:#aaa;")
        else:
            text_label.setStyleSheet("color:#333;")

        # 优先级标记
        pri_marks = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        pri_label = QLabel(pri_marks.get(pri, "🟡"))
        pri_label.setFixedWidth(20)

        # 完成标记
        done_label = QLabel("✅" if done else "")
        done_label.setFixedWidth(20)

        row = QHBoxLayout()
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)
        row.addWidget(bar)
        row.addWidget(time_label)
        row.addWidget(text_label, 1)
        row.addWidget(pri_label)
        row.addWidget(done_label)

        card.setLayout(row)
        return card

    def open_memo_edit(self):
        self.close()
        dlg = MemoEditDialog(self.target_date, self._theme, self.parent())
        dlg.exec()
