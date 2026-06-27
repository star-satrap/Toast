import argparse
import json
import sys
import time
from functools import cmp_to_key

try:
    import ctypes
    _user32 = ctypes.windll.user32
    _VK_LBUTTON = 0x01
except (ImportError, AttributeError):
    _user32 = None
    _VK_LBUTTON = 0

from PySide6 import QtCore, QtWidgets, QtGui, QtNetwork
from PySide6.QtCore import QLocale

# 新建项目环境改用：
# uv venv --seed
# --seed 参数会自动预装 pip、setuptools，后续 pyside6-deploy、pyinstaller 这类打包工具就不会缺 pip。

# pyside6 版本： pip install pyside6==6.7.3 | 6.7.3版本适用于Windows Server 2016
# 部署命令 pyside6-deploy .\toast.py

# ========== 全局配置 ==========
TOAST_OPACITY = 0.88  # 统一透明度控制（0.85 ~ 0.9）

# 支持的语言
LANG = "en"
sys_locale = QLocale.system()

# 优先看 UI 语言列表
ui_langs = sys_locale.uiLanguages()
if any(ls.lower().startswith("zh") for ls in ui_langs):
    LANG = "zh"

STRINGS = {
    "default_title": {"en": "Default Notification", "zh": "默认通知"},
    "default_message": {"en": "This is a test message", "zh": "这是一个测试消息"},
    "pin_tooltip_pin": {"en": "Pin", "zh": "置顶"},
    "pin_tooltip_unpin": {"en": "Unpin", "zh": "取消置顶"},
    "close_all_tooltip": {"en": "Close all notifications and exit", "zh": "关闭所有通知并退出程序"},
    "countdown_prefix": {"en": "Remaining: ", "zh": "剩余时间："},
    "days": {"en": "d ", "zh": "天"},
    "hours": {"en": "h ", "zh": "小时"},
    "minutes": {"en": "m ", "zh": "分钟"},
    "seconds": {"en": "s", "zh": "秒钟"},
    "expired_label": {"en": "Expired", "zh": "已过期"},
    "expired_history_tooltip": {"en": "Expired history", "zh": "已过期记录"},
    "expired_history_empty": {"en": "No expired records", "zh": "暂无过期记录"},
    "expired_summary": {"en": "Expired: {n}", "zh": "已过期：{n} 条"},
}


def tr(key: str) -> str:
    return STRINGS.get(key, {}).get(LANG, key)


# ========== 到期历史数据结构 ==========
class ExpiredRecord:
    """单条过期记录（内存维护，不持久化）"""
    __slots__ = ("title", "message", "created_at", "expired_at")

    def __init__(self, title: str, message: str, created_at: float, expired_at: float):
        self.title = title
        self.message = message
        self.created_at = created_at
        self.expired_at = expired_at


class ExpiredHistory:
    """FIFO 过期记录集合，最大 100 条"""
    MAX_RECORDS = 100

    def __init__(self):
        self._records = []

    def add(self, record: ExpiredRecord):
        self._records.append(record)
        # FIFO 淘汰
        if len(self._records) > self.MAX_RECORDS:
            self._records.pop(0)

    def all(self):
        return list(self._records)

    def count(self):
        return len(self._records)

    def clear(self):
        self._records.clear()


# ========== 自定义按钮基类 ==========
class ToolButton(QtWidgets.QToolButton):
    """带 tooltip 提示的基础按钮"""
    def enterEvent(self, event):
        if self.toolTip():
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)


# ========== Windows 原生风格关闭按钮 ==========
class CloseButton(ToolButton):
    """红色背景 + 白色 ✕，hover 时加深，使用 QPainter 自绘"""
    def __init__(self, theme="dark"):
        super().__init__()
        self.theme = theme
        self.setMinimumSize(22, 22)
        self.setMaximumSize(22, 22)
        self._hovered = False
        self._pressed = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 背景色：默认红 → hover 加深 → pressed 更深
        if self._pressed:
            color = QtGui.QColor(180, 10, 25)
        elif self._hovered:
            color = QtGui.QColor(232, 17, 35)
        else:
            color = QtGui.QColor(200, 35, 45)
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 4, 4)

        # 白色 ✕
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255), 1.5)
        painter.setPen(pen)
        m = 6
        painter.drawLine(rect.left() + m, rect.top() + m,
                         rect.right() - m, rect.bottom() - m)
        painter.drawLine(rect.right() - m, rect.top() + m,
                         rect.left() + m, rect.bottom() - m)


# ========== LED 信号灯置顶按钮 ==========
class LedPinButton(ToolButton):
    """圆形 LED 指示灯：置顶时绿色亮起（带发光），取消置顶时灰色熄灭"""
    def __init__(self, theme="dark"):
        super().__init__()
        self.theme = theme
        self.pinned = True
        self.setMinimumSize(22, 22)
        self.setMaximumSize(22, 22)
        self._hovered = False

    def set_pinned(self, pinned):
        self.pinned = pinned
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        cx = rect.width() / 2
        cy = rect.height() / 2
        radius = min(rect.width(), rect.height()) / 2 - 3

        # 外发光（仅亮起时）
        if self.pinned:
            glow = QtGui.QRadialGradient(cx, cy, radius * 2)
            glow.setColorAt(0, QtGui.QColor(0, 255, 0, 60))
            glow.setColorAt(1, QtGui.QColor(0, 255, 0, 0))
            painter.setBrush(glow)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawEllipse(QtCore.QPointF(cx, cy), radius * 2, radius * 2)

        # LED 主体：径向渐变模拟立体感
        gradient = QtGui.QRadialGradient(
            cx - radius * 0.3, cy - radius * 0.3, radius * 1.2
        )
        if self.pinned:
            gradient.setColorAt(0, QtGui.QColor(120, 255, 120))
            gradient.setColorAt(0.6, QtGui.QColor(0, 200, 0))
            gradient.setColorAt(1, QtGui.QColor(0, 100, 0))
        else:
            gradient.setColorAt(0, QtGui.QColor(150, 150, 150))
            gradient.setColorAt(0.6, QtGui.QColor(100, 100, 100))
            gradient.setColorAt(1, QtGui.QColor(50, 50, 50))

        painter.setBrush(gradient)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 100), 1))
        painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

        # hover 边框
        if self._hovered:
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 191, 255), 1.5))
            painter.drawEllipse(QtCore.QPointF(cx, cy), radius + 2, radius + 2)


# ========== 到期摘要行（固定位置，始终可见） ==========
class ExpiredSummaryRow(QtWidgets.QWidget):
    """工具栏下方、toast 列表上方的固定摘要行
    显示过期记录数量；hover/点击触发浮层。"""
    hover_enter = QtCore.Signal()
    hover_leave = QtCore.Signal()
    clicked = QtCore.Signal()  # 点击摘要行（用于切换浮层）

    def __init__(self, theme="dark"):
        super().__init__()
        self.theme = theme
        self._count = 0
        self._hovered = False
        self.setFixedHeight(24)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def sizeHint(self):
        return QtCore.QSize(-1, 24)

    def _apply_style(self):
        if self.theme == "light":
            self._color_has = "#333"
            self._color_empty = "#aaa"
            self._bar_has = QtGui.QColor(255, 140, 0)       # 橙色
            self._bar_empty = QtGui.QColor(204, 204, 204)   # 灰色
            self._bg_normal = QtGui.QColor(245, 245, 245, 180)   # 浅灰底
            self._bg_hover = QtGui.QColor(235, 235, 235, 220)    # hover 加深
        else:
            self._color_has = "#ddd"
            self._color_empty = "#666"
            self._bar_has = QtGui.QColor(255, 165, 0)       # 橙色
            self._bar_empty = QtGui.QColor(68, 68, 68)     # 灰色
            self._bg_normal = QtGui.QColor(30, 30, 30, 180)      # 深灰底
            self._bg_hover = QtGui.QColor(45, 45, 45, 220)       # hover 加深
        self.update()

    def set_count(self, count: int):
        self._count = count
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        self.hover_enter.emit()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        self.hover_leave.emit()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 圆角背景填充（hover 时加深，增强可点击感）
        bg = self._bg_hover if self._hovered else self._bg_normal
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 4, 4)

        # 左侧竖条（3px 宽，加粗增强视觉关联）
        bar_color = self._bar_has if self._count > 0 else self._bar_empty
        painter.setBrush(bar_color)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(0, 3, 3, rect.height() - 6), 1.5, 1.5)
        painter.drawPath(path)

        # 文字
        if self._count > 0:
            text = tr("expired_summary").replace("{n}", str(self._count))
            color = QtGui.QColor(self._color_has)
        else:
            text = tr("expired_history_empty")
            color = QtGui.QColor(self._color_empty)

        if self._hovered:
            color = color.lighter(130)

        painter.setPen(QtGui.QPen(color))
        font = QtGui.QFont("Microsoft YaHei", 9)
        font.setBold(self._count > 0)
        painter.setFont(font)
        text_rect = QtCore.QRect(10, 0, rect.width() - 30, rect.height())
        painter.drawText(text_rect,
                         QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
                         text)

        # 右侧箭头提示（hover 时显示，暗示可展开）
        if self._hovered and self._count > 0:
            painter.setPen(QtGui.QPen(color, 1.5))
            ax = rect.right() - 12
            ay = rect.height() / 2
            painter.drawLine(ax - 4, ay - 3, ax, ay)
            painter.drawLine(ax, ay, ax - 4, ay + 3)


# ========== 到期历史浮层（遮盖 toast 区域） ==========
class ExpiredOverlay(QtWidgets.QWidget):
    """半透明遮罩浮层，覆盖 container 的 toast 区域
    显示过期记录列表，支持 hover 宽限期和 click 锁定两种触发模式。"""
    request_show = QtCore.Signal()
    request_hide = QtCore.Signal()
    overlay_hidden = QtCore.Signal()  # 淡出动画结束后发射，用于卸载事件过滤器

    def __init__(self, theme="dark"):
        super().__init__()
        self.theme = theme
        self._records = []
        self._opacity_anim = None
        # 触发模式
        self._click_locked = False
        self._hover_grace_timer = None
        self._hover_active = False  # 鼠标是否在浮层内

        # 浮层作为独立顶层窗口，初始隐藏
        self.setVisible(False)
        # WA_OpaquePaintEvent：告知 Qt 此 widget 在 paintEvent 中绘制全部区域，
        # Qt 无需在 paintEvent 前填充默认背景色（白色）
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
        # 顶层窗口使用 windowOpacity 控制透明度（避免 QGraphicsOpacityEffect 渲染白框）
        self.setWindowOpacity(0.0)

        # 主布局：QScrollArea 内含记录列表
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_layout.setSpacing(1)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        # viewport 和 content 都不自动填充背景，让 paintEvent 背景透出
        self.scroll.viewport().setAutoFillBackground(False)
        self.content.setAutoFillBackground(False)
        outer.addWidget(self.scroll)

        self._apply_theme_style()

    def paintEvent(self, event):
        """手动绘制纯色背景（覆盖窗口默认白色表面）"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if self.theme == "dark":
            bg_color = QtGui.QColor("#1a1a1a")
        else:
            bg_color = QtGui.QColor("#f0f0f0")
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        # 填充整个矩形，覆盖窗口默认白色表面
        painter.drawRect(self.rect())

    def resizeEvent(self, event):
        """窗口尺寸变化时裁剪为 8px 圆角矩形（与 ToastContainer 圆角风格一致）"""
        super().resizeEvent(event)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), 8, 8)
        polygon = path.toFillPolygon().toPolygon()
        self.setMask(QtGui.QRegion(polygon))

    def _apply_theme_style(self):
        """主题滚动条样式"""
        if self.theme == "light":
            text_color = "#333"
            separator = "rgba(0,0,0,20)"
            scroll_bg = "rgba(220,220,220,160)"
            handle = "#999"
        else:
            text_color = "#ddd"
            separator = "rgba(255,255,255,20)"
            scroll_bg = "rgba(30,30,30,160)"
            handle = "#888"

        self.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {scroll_bg};
                width: 8px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {handle};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        self._text_color = text_color
        self._separator = separator

    def set_records(self, records):
        """刷新记录列表（最新过期在最上方，倒序）"""
        # 清空旧条目（保留末尾 stretch）
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()

        self._records = list(reversed(records))

        if not self._records:
            empty = QtWidgets.QLabel(tr("expired_history_empty"))
            empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {self._text_color}; background: transparent; font-size: 9pt;")
            self.content_layout.insertWidget(0, empty)
            return

        # 选择等宽字体
        mono_font = self._pick_mono_font()
        for rec in self._records:
            row = self._build_row(rec, mono_font)
            self.content_layout.insertWidget(self.content_layout.count() - 1, row)

    def _pick_mono_font(self):
        """优先使用 Consolas / Courier New，否则用默认字体"""
        font_families = QtGui.QFontDatabase.families()
        for candidate in ("Consolas", "Courier New", "DejaVu Sans Mono"):
            if any(c == candidate for c in font_families):
                return QtGui.QFont(candidate, 9)
        return QtGui.QFont("Microsoft YaHei", 9)

    def _build_row(self, rec: ExpiredRecord, mono_font: QtGui.QFont) -> QtWidgets.QWidget:
        row = QtWidgets.QFrame()
        row.setObjectName("overlayRow")
        row.setStyleSheet(f"""
            QFrame#overlayRow {{
                border-bottom: 1px solid {self._separator};
                background: transparent;
            }}
        """)
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(2, 2, 2, 2)
        row_layout.setSpacing(12)

        # 左侧：开始时间 ~ 到期时间（等宽）
        start_str = time.strftime("%H:%M:%S", time.localtime(rec.created_at))
        end_str = time.strftime("%H:%M:%S", time.localtime(rec.expired_at))
        time_text = f"{start_str} ~ {end_str}"
        time_lbl = QtWidgets.QLabel(time_text)
        time_lbl.setFont(mono_font)
        time_lbl.setStyleSheet(f"color: {self._text_color}; background: transparent;")

        # 右侧：标题加粗 + " | " + 消息摘要（≤40 字符）
        title_text = (rec.title or "").strip()[:20]
        msg_text = (rec.message or "").strip()[:40]
        desc_text = f"<b>{title_text}</b> | {msg_text}"
        desc_lbl = QtWidgets.QLabel(desc_text)
        desc_lbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
        desc_lbl.setStyleSheet(f"color: {self._text_color}; background: transparent; font-size: 8.5pt;")

        row_layout.addWidget(time_lbl, 0)
        row_layout.addWidget(desc_lbl, 1)
        return row

    # ========== 触发与关闭 ==========
    def enterEvent(self, event):
        # 鼠标进入浮层 → 取消宽限期定时器，保持显示
        self._hover_active = True
        if self._hover_grace_timer is not None:
            self._hover_grace_timer.stop()
            self._hover_grace_timer = None
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 鼠标离开浮层 → 若非 click 锁定则关闭
        self._hover_active = False
        if not self._click_locked:
            self.request_hide.emit()
        super().leaveEvent(event)

    def start_hover_grace(self):
        """摘要行 hover_leave 时调用，启动 250ms 宽限期"""
        if self._click_locked:
            return
        if self._hover_grace_timer is not None:
            self._hover_grace_timer.stop()
        self._hover_grace_timer = QtCore.QTimer(self)
        self._hover_grace_timer.setSingleShot(True)
        self._hover_grace_timer.setInterval(250)
        self._hover_grace_timer.timeout.connect(lambda: self._on_grace_timeout())
        self._hover_grace_timer.start()

    def cancel_hover_grace(self):
        """摘要行 hover_enter 时调用，取消宽限期"""
        if self._hover_grace_timer is not None:
            self._hover_grace_timer.stop()
            self._hover_grace_timer = None

    def _on_grace_timeout(self):
        """宽限期结束，鼠标未进入浮层 → 关闭"""
        self._hover_grace_timer = None
        if not self._hover_active and not self._click_locked:
            self.request_hide.emit()

    def set_click_locked(self, locked: bool):
        self._click_locked = locked

    def is_click_locked(self) -> bool:
        return self._click_locked

    # ========== 出现/消失动画 ==========
    def show_overlay(self):
        if self.isVisible() and self.windowOpacity() >= 0.99:
            return
        self.show()
        self.raise_()
        if self._opacity_anim is not None:
            try:
                self._opacity_anim.stop()
            except RuntimeError:
                pass
            self._opacity_anim = None
        anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(150)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(1.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._opacity_anim = anim

    def hide_overlay(self):
        if not self.isVisible():
            return
        if self._opacity_anim is not None:
            try:
                self._opacity_anim.stop()
            except RuntimeError:
                pass
            self._opacity_anim = None
        anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(100)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        # 合并为单个 slot：确保 hide() 失败也不影响 overlay_hidden 信号发射
        anim.finished.connect(self._on_hide_anim_finished)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._opacity_anim = anim

    def _on_hide_anim_finished(self):
        """hide_overlay 动画结束：隐藏窗口并发射 overlay_hidden 信号"""
        try:
            self.hide()
        except RuntimeError:
            pass
        self.overlay_hidden.emit()

    def sizeHint(self):
        # 给一个合理的最小高度，防止被压缩到接近 0
        h = max(120, super().sizeHint().height())
        w = max(260, super().sizeHint().width())
        return QtCore.QSize(w, h)


# ========== 单个通知 ==========
class Toast(QtWidgets.QFrame):
    closed = QtCore.Signal(object)
    remaining_changed = QtCore.Signal()
    expired = QtCore.Signal(object)  # 进入 EXPIRED 阶段时发射（携带 self）

    def __init__(self, title, message, duration=3000, show_countdown=False, theme="dark"):
        super().__init__()
        self.setObjectName("toast")
        self.title = title or tr("default_title")
        self.message = message or tr("default_message")
        self.created_at = time.time()
        self.duration = duration
        self.remaining = max(1, duration // 1000)
        self.show_countdown = show_countdown
        self.theme = theme
        self._fade_anim = None
        self._exit_anim = None

        # 到期缓冲：两阶段生命周期
        self.phase = "active"          # "active" | "expired"
        self.expired_time = None       # 进入过期阶段的时间戳
        self._insert_order = 0         # 插入顺序（用于无倒计时排序）

        # 右滑关闭手势状态（Windows 平板触摸适配）
        self._drag = None
        self._drag_direction = None    # None | "horizontal" | "vertical" 方向锁
        self._slide_back_anim = None
        self._swipe_threshold = 0.5
        self._fling_velocity = 600.0
        self._direction_lock_threshold = 10  # 锁定方向的距离阈值

        # 动画状态标记
        self._exiting = False
        self._entering = False

        # 主题样式搭配（字体 12pt → 10pt，圆角 12px → 10px）
        if theme == "light":
            self._base_style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(255,255,255,220), stop:1 rgba(240,240,240,180));
                    border-radius: 10px;
                    border: 1px solid rgba(0,0,0,40);
                }
                QLabel { color: black; font-size: 10pt; background: transparent; }
            """
            self._expired_style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(255,255,255,220), stop:1 rgba(240,240,240,180));
                    border-radius: 10px;
                    border: 1px solid rgba(255,140,0,200);
                }
                QLabel { color: black; font-size: 10pt; background: transparent; }
            """
            countdown_color = "blue"
        else:
            self._base_style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(40,40,40,220), stop:1 rgba(20,20,20,180));
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,40);
                }
                QLabel { color: white; font-size: 10pt; background: transparent; }
            """
            self._expired_style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(40,40,40,220), stop:1 rgba(20,20,20,180));
                    border-radius: 10px;
                    border: 1px solid rgba(255,165,0,180);
                }
                QLabel { color: white; font-size: 10pt; background: transparent; }
            """
            countdown_color = "yellow"

        self.setStyleSheet(self._base_style)

        # 阴影
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        # 布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 8)
        layout.setSpacing(4)

        # 标题 + 关闭
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.setSpacing(4)
        title_lbl = QtWidgets.QLabel(f"<b>{title or tr('default_title')}</b>")
        close_btn = CloseButton(theme=theme)
        close_btn.clicked.connect(self._manual_close)
        top_layout.addWidget(title_lbl)
        top_layout.addStretch()
        top_layout.addWidget(close_btn)
        layout.addLayout(top_layout)

        # 文本
        msg_lbl = QtWidgets.QLabel(message or tr("default_message"))
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        # 倒计时
        self.countdown_lbl = QtWidgets.QLabel("")
        self.countdown_lbl.setStyleSheet(
            f"color: {countdown_color}; font-weight: bold; font-size: 9pt; background: transparent;"
        )
        layout.addWidget(self.countdown_lbl)

        # 让标题/正文/倒计时区域鼠标事件穿透，使整张卡片可接收右滑手势
        title_lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        msg_lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.countdown_lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 生命周期管理
        if self.show_countdown:
            # 倒计时 toast：tick 驱动生命周期
            self._update_countdown()
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(1000)
        else:
            # 非倒计时 toast：duration 到期直接出场
            QtCore.QTimer.singleShot(self.duration, self.start_exit_anim)

    def showEvent(self, event):
        super().showEvent(event)
        # 入场动画由容器 add_toast 驱动，这里仅设置初始透明度
        self.setWindowOpacity(0)

    # ========== 倒计时与到期缓冲 ==========
    def _tick(self):
        if self.phase != "active":
            return
        self.remaining -= 1
        if self.remaining <= 0:
            self._enter_expired_phase()
        else:
            self._update_countdown()
            self.remaining_changed.emit()

    def _enter_expired_phase(self):
        """进入已过期阶段"""
        self.phase = "expired"
        self.expired_time = time.time()
        if hasattr(self, "_timer"):
            self._timer.stop()
        # 视觉变化
        self.countdown_lbl.setText(tr("expired_label"))
        self.setStyleSheet(self._expired_style)
        # 5 秒后自动出场
        QtCore.QTimer.singleShot(5000, self.start_exit_anim)
        # 通知管理器记录过期（phase 切换瞬间）
        self.expired.emit(self)
        self.remaining_changed.emit()

    def _update_countdown(self):
        sec = max(0, self.remaining)
        days, sec = divmod(sec, 86400)
        hours, sec = divmod(sec, 3600)
        minutes, sec = divmod(sec, 60)
        parts = []
        if days:
            parts.append(f"{days}{tr('days')}")
        if hours:
            parts.append(f"{hours}{tr('hours')}")
        if minutes:
            parts.append(f"{minutes}{tr('minutes')}")
        parts.append(f"{sec}{tr('seconds')}")
        self.countdown_lbl.setText(tr("countdown_prefix") + "".join(parts))

    # ========== 统一出场动画（右滑 + 淡出） ==========
    def _manual_close(self):
        self.start_exit_anim()

    def start_exit_anim(self):
        if self._exiting:
            return
        self._exiting = True

        # 记录当前几何，提到最上层做滑出动画
        # 不在动画前 removeWidget，避免其他 toast 立即重排
        # 真正的移除交给 _final_close → _on_closed → remove_toast
        current_geo = QtCore.QRect(self.geometry())
        self.raise_()

        # 终止位置：向右偏移自身宽度
        exit_geo = QtCore.QRect(current_geo)
        exit_geo.moveLeft(exit_geo.left() + self.width())

        anim_group = QtCore.QParallelAnimationGroup(self)

        fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        fade_anim.setDuration(150)
        fade_anim.setStartValue(self.windowOpacity())
        fade_anim.setEndValue(0)
        fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)

        slide_anim = QtCore.QPropertyAnimation(self, b"geometry", self)
        slide_anim.setDuration(150)
        slide_anim.setStartValue(current_geo)
        slide_anim.setEndValue(exit_geo)
        slide_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)

        anim_group.addAnimation(fade_anim)
        anim_group.addAnimation(slide_anim)
        anim_group.finished.connect(self._final_close)
        anim_group.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._exit_anim = anim_group

    def _final_close(self):
        self.closed.emit(self)
        self.deleteLater()

    # ========== 右滑关闭手势（触摸跟手 + 方向锁） ==========
    def _find_scroll_area(self):
        """向上查找祖先 QScrollArea（用于垂直滚动方向）"""
        p = self.parent()
        while p is not None:
            if isinstance(p, QtWidgets.QScrollArea):
                return p
            p = p.parent()
        return None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._drag is None:
            gp = event.globalPosition().toPoint()
            self._drag = {
                "start_global": gp,
                "origin_geo": self.geometry(),
                "last_x": gp.x(),
                "last_y": gp.y(),
                "init_scroll": self._get_scroll_value(),
                "last_time": time.perf_counter(),
                "velocity": 0.0,
                "moved": False,
            }
            self._drag_direction = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag:
            gp = event.globalPosition().toPoint()
            delta = gp - self._drag["start_global"]

            # 方向锁定：首次位移超过阈值时锁定方向
            if self._drag_direction is None:
                dist = max(abs(delta.x()), abs(delta.y()))
                if dist >= self._direction_lock_threshold:
                    if abs(delta.y()) > abs(delta.x()):
                        self._drag_direction = "vertical"
                    else:
                        self._drag_direction = "horizontal"

            if self._drag_direction == "vertical":
                # 垂直方向 → 交给父 QScrollArea 处理滚动
                dy = gp.y() - self._drag["last_y"]
                self._scroll_by(-dy)
                self._drag["last_y"] = gp.y()
                self._drag["moved"] = True  # 标记已处理，避免 press 误触发按钮
                return  # 不调用 super，避免布局/位置干扰

            if self._drag_direction == "horizontal":
                dx = max(0, delta.x())
                if dx > 2:
                    self._drag["moved"] = True
                self.setGeometry(self._drag["origin_geo"].translated(dx, 0))
                now = time.perf_counter()
                dt = now - self._drag["last_time"]
                if dt > 0:
                    inst = (gp.x() - self._drag["last_x"]) / dt
                    self._drag["velocity"] = 0.6 * inst + 0.4 * self._drag["velocity"]
                self._drag["last_time"] = now
                self._drag["last_x"] = gp.x()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag and self._drag.get("moved"):
            # 垂直滚动方向：无需关闭 toast
            if self._drag_direction == "vertical":
                self._drag = None
                self._drag_direction = None
                return
            # 水平方向：根据阈值/速度判定是否关闭
            origin_x = self._drag["origin_geo"].x()
            offset = self.geometry().x() - origin_x
            velocity = self._drag["velocity"]
            width = self.width() or 1
            if offset >= width * self._swipe_threshold or velocity >= self._fling_velocity:
                self._drag = None
                self._drag_direction = None
                self.start_exit_anim()
                return
            self._animate_back_to(self._drag["origin_geo"])
            self._drag = None
            self._drag_direction = None
            return
        self._drag = None
        self._drag_direction = None
        super().mouseReleaseEvent(event)

    def _get_scroll_value(self):
        sa = self._find_scroll_area()
        if sa is None:
            return 0
        return sa.verticalScrollBar().value()

    def _scroll_by(self, dy):
        sa = self._find_scroll_area()
        if sa is None:
            return
        bar = sa.verticalScrollBar()
        bar.setValue(bar.value() + int(dy))

    def _animate_back_to(self, geo):
        self._slide_back_anim = QtCore.QPropertyAnimation(self, b"geometry", self)
        self._slide_back_anim.setDuration(200)
        self._slide_back_anim.setStartValue(self.geometry())
        self._slide_back_anim.setEndValue(geo)
        self._slide_back_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._slide_back_anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


# ========== 容器 ==========
class ToastContainer(QtWidgets.QWidget):
    def __init__(self, theme="dark", no_expired_history=False):
        super().__init__(None, QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint |
                         QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.theme = theme
        self.no_expired_history = no_expired_history
        self.pinned = True
        self.margin = 50
        self.screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.max_height = self.screen.height() - 2 * self.margin
        self.width = 300

        # 批量插入错峰计数
        self._stagger_count = 0
        self._insert_counter = 0

        # 到期列表：摘要行 + 浮层（no_expired_history=True 时不创建）
        self.summary_row = None
        self.overlay = None
        self._height_anim = None  # 容器高度过渡动画
        self._outside_click_timer = None  # 浮层外部点击检测定时器

        # 初始位置（靠右上）
        init_h = 120
        self.setGeometry(
            self.screen.right() - self.width - self.margin,
            self.screen.top() + self.margin,
            self.width,
            init_h
        )

        # 顶部工具栏
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(4, 4, 4, 3)
        toolbar.setSpacing(4)

        self.pin_btn = LedPinButton(theme=theme)
        self.pin_btn.setToolTip(tr("pin_tooltip_pin"))
        self.pin_btn.clicked.connect(self.toggle_pin)

        self.close_all_btn = CloseButton(theme=theme)
        self.close_all_btn.setToolTip(tr("close_all_tooltip"))
        self.close_all_btn.clicked.connect(QtWidgets.QApplication.quit)

        toolbar.addWidget(self.pin_btn)
        toolbar.addWidget(self.close_all_btn)
        toolbar.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        # container（toast 列表）
        self.container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(6, 4, 6, 6)
        self.vbox.setSpacing(6)
        self.vbox.addStretch()

        # root 布局：[toolbar] + [summary_row] + [container/scroll]
        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(4, 4, 4, 4)
        self.root.setSpacing(3)
        self.root.addLayout(toolbar)

        # 摘要行（始终固定可见，位于 toolbar 和 container 之间）
        if not self.no_expired_history:
            self.summary_row = ExpiredSummaryRow(theme=theme)
            self.summary_row.hover_enter.connect(self._on_summary_hover_enter)
            self.summary_row.hover_leave.connect(self._on_summary_hover_leave)
            self.summary_row.clicked.connect(self._on_summary_clicked)
            self.root.addWidget(self.summary_row)

            # 浮层（独立顶层窗口，不受容器高度裁剪）
            self.overlay = ExpiredOverlay(theme=theme)
            self.overlay.setParent(None)
            self.overlay.setWindowFlags(
                QtCore.Qt.WindowType.Tool |
                QtCore.Qt.WindowType.FramelessWindowHint |
                QtCore.Qt.WindowType.WindowStaysOnTopHint
            )
            # self.overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
            self.overlay.request_show.connect(self._show_overlay)
            self.overlay.request_hide.connect(self._hide_overlay)
            # 浮层淡出结束后卸载事件过滤器
            self.overlay.overlay_hidden.connect(self._on_overlay_hidden)

        self.root.addWidget(self.container)

        self.scroll = None
        self.setStyleSheet("background: transparent; border-radius: 10px;")

        self.show()
        self.setWindowOpacity(TOAST_OPACITY)

    # ========== 到期列表触发逻辑 ==========
    def _on_summary_hover_enter(self):
        """鼠标进入摘要行：若非 click 锁定则显示浮层"""
        if self.no_expired_history or self.overlay is None:
            return
        if self.overlay.is_click_locked():
            return  # click 锁定时 hover 不响应
        # 取消宽限期（如果有）
        self.overlay.cancel_hover_grace()
        # 仅当有记录时才显示浮层
        if self._expired_count > 0:
            self._show_overlay()

    def _on_summary_hover_leave(self):
        """鼠标离开摘要行：启动 250ms 宽限期"""
        if self.no_expired_history or self.overlay is None:
            return
        if self.overlay.is_click_locked():
            return
        self.overlay.start_hover_grace()

    def _on_summary_clicked(self):
        """点击摘要行：切换 click 锁定模式"""
        if self.no_expired_history or self.overlay is None:
            return
        if self._expired_count <= 0:
            return  # 无记录时不响应
        if self.overlay.is_click_locked():
            # 已锁定 → 关闭浮层，退出锁定
            self.overlay.set_click_locked(False)
            self._stop_outside_click_detection()
            self._hide_overlay()
        else:
            # 未锁定 → 显示浮层，进入锁定
            self._show_overlay()
            self.overlay.set_click_locked(True)
            self._start_outside_click_detection()

    def eventFilter(self, obj, event):
        """全局事件过滤器：click 锁定模式下检测 Qt 应用内的鼠标按下。
        过滤器安装在 QApplication.instance() 上。
        - 点击在摘要行范围内 → 放行（让摘要行 clicked 信号处理 toggle 关闭）
        - 点击在浮层范围内 → 放行（让浮层正常处理滚动/子 widget 交互）
        - 点击在 Qt 应用其他位置 → 关闭浮层，放行事件
        注意：点击桌面/其他应用不经过 Qt 事件循环，由 _outside_click_timer 轮询检测。"""
        if (self.overlay is not None and self.overlay.is_click_locked()
                and event.type() == QtCore.QEvent.Type.MouseButtonPress
                and isinstance(event, QtGui.QMouseEvent)):
            gp = event.globalPosition().toPoint()
            # 点击在摘要行内 → 放行（toggle 由 _on_summary_clicked 处理）
            if self.summary_row is not None:
                summary_local = self.summary_row.mapFromGlobal(gp)
                if self.summary_row.rect().contains(summary_local):
                    return False
            # 点击在浮层内 → 放行（让浮层处理滚动等交互）
            if self.overlay.isVisible():
                overlay_local = self.overlay.mapFromGlobal(gp)
                if self.overlay.rect().contains(overlay_local):
                    return False
            # 其他位置 → 关闭浮层，放行事件（不干扰目标 widget 响应）
            self.overlay.set_click_locked(False)
            self._hide_overlay()
            return False
        return super().eventFilter(obj, event)

    # ========== 浮层外部点击检测（Windows 原生轮询）==========
    def _start_outside_click_detection(self):
        """启动外部点击检测定时器（仅 click 锁定模式下使用）"""
        if _user32 is None:
            return  # 非 Windows 平台不启用
        if self._outside_click_timer is None:
            self._outside_click_timer = QtCore.QTimer(self)
            self._outside_click_timer.setTimerType(
                QtCore.Qt.TimerType.PreciseTimer)
            self._outside_click_timer.timeout.connect(self._check_outside_click)
        self._outside_click_timer.start(30)  # 30ms 轮询

    def _stop_outside_click_detection(self):
        """停止外部点击检测定时器"""
        if self._outside_click_timer is not None:
            self._outside_click_timer.stop()

    def _check_outside_click(self):
        """轮询检测鼠标左键是否在浮层和摘要行外按下。
        使用 Windows API GetAsyncKeyState 获取全局鼠标状态，
        不依赖 Qt 事件循环（可捕获桌面/其他应用的点击）。"""
        if not self.overlay or not self.overlay.is_click_locked():
            self._stop_outside_click_detection()
            return
        # 获取全局鼠标左键状态（不依赖 Qt 事件循环）
        if not (_user32.GetAsyncKeyState(_VK_LBUTTON) & 0x8000):
            return  # 左键未按下
        # 左键按下，检查鼠标位置是否在浮层和摘要行外
        pos = QtGui.QCursor.pos()
        # 在浮层内 → 不关闭（让浮层处理交互）
        if self.overlay.isVisible():
            overlay_local = self.overlay.mapFromGlobal(pos)
            if self.overlay.rect().contains(overlay_local):
                return
        # 在摘要行内 → 不关闭（让 clicked 信号处理 toggle）
        if self.summary_row is not None:
            summary_local = self.summary_row.mapFromGlobal(pos)
            if self.summary_row.rect().contains(summary_local):
                return
        # 在外部按下 → 关闭浮层
        self.overlay.set_click_locked(False)
        self._hide_overlay()

    def _show_overlay(self):
        """显示浮层（同步尺寸后淡入）"""
        if self.no_expired_history or self.overlay is None:
            return
        if self._expired_count <= 0:
            return
        self._sync_overlay_geometry()
        # 全局事件过滤器：捕获应用内任意位置的鼠标按下（桌面、其他 widget 等）
        QtWidgets.QApplication.instance().installEventFilter(self)
        self.overlay.show_overlay()

    def _hide_overlay(self):
        """隐藏浮层（淡出）"""
        if self.no_expired_history or self.overlay is None:
            return
        self.overlay.hide_overlay()

    def _on_overlay_hidden(self):
        """浮层淡出动画结束后卸载全局事件过滤器"""
        if self.overlay is not None:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        self._stop_outside_click_detection()

    def _sync_overlay_geometry(self):
        """浮层独立顶层窗口定位：使用屏幕绝对坐标。
        浮层左上角与容器左边缘对齐，y = 摘要行底部 + spacing。
        高度 = min(300, max(120, 屏幕可用空间))。"""
        if self.overlay is None:
            return
        # 起始 y（容器局部坐标）：摘要行底部 + spacing
        if self.summary_row is not None:
            local_y = self.summary_row.geometry().bottom() + self.root.spacing()
        else:
            # 防御性处理：无摘要行时从 container 顶部开始
            target = self.scroll if self.scroll is not None else self.container
            local_y = target.geometry().y() if target else 0

        # 转换为屏幕绝对坐标
        overlay_y = self.mapToGlobal(QtCore.QPoint(0, local_y)).y()
        # x = 容器左边缘（屏幕绝对 x）
        overlay_x = self.geometry().x()

        # 可用空间
        available_h = self.screen.bottom() - self.margin - overlay_y
        overlay_h = max(120, min(300, available_h))
        overlay_w = self.width

        self.overlay.setGeometry(overlay_x, overlay_y, overlay_w, overlay_h)
        self.overlay.raise_()

    @property
    def _expired_count(self):
        """当前过期记录数量（由 ToastManager 维护并通过 refresh_expired_history 更新）"""
        return getattr(self, '_expired_count_value', 0)

    @_expired_count.setter
    def _expired_count(self, value):
        self._expired_count_value = value

    def refresh_expired_history(self, records):
        """刷新到期历史：更新摘要行数字 + 浮层记录列表"""
        if self.no_expired_history:
            return
        count = len(records)
        self._expired_count = count
        if self.summary_row is not None:
            self.summary_row.set_count(count)
        if self.overlay is not None:
            self.overlay.set_records(records)
            # 如果浮层当前可见，刷新内容（无需调整容器高度，浮层是覆盖式的）
            # 但需要同步尺寸以防 container 尺寸变化
            if self.overlay.isVisible():
                self._sync_overlay_geometry()

    def _apply_scrollbar_style(self):
        """为主滚动条应用主题样式"""
        if self.scroll is None:
            return
        if self.theme == "light":
            handle = "#999"
            bg = "rgba(220,220,220,160)"
        else:
            handle = "#888"
            bg = "rgba(30,30,30,160)"
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {bg};
                width: 8px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {handle};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {handle};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

    def toggle_pin(self):
        self.pinned = not self.pinned
        flags = QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint
        if self.pinned:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
            self.pin_btn.set_pinned(True)
            self.pin_btn.setToolTip(tr("pin_tooltip_pin"))
        else:
            self.pin_btn.set_pinned(False)
            self.pin_btn.setToolTip(tr("pin_tooltip_unpin"))
        self.setWindowFlags(flags)
        self.show()
        self.setWindowOpacity(TOAST_OPACITY)
        # toggle_pin 会触发 hide + show，浮层为独立窗口需重新同步层级
        if self.overlay is not None and self.overlay.isVisible():
            self._sync_overlay_geometry()
            self.overlay.raise_()

    def add_toast(self, toast):
        # 设置插入顺序
        toast._insert_order = self._insert_counter
        self._insert_counter += 1

        # 智能插入位置：有倒计时 toast 找到第一个 remaining 更大的位置
        insert_index = self.vbox.count() - 1  # 默认在 stretch 前面（末尾）
        if toast.show_countdown and toast.phase == "active":
            for i in range(self.vbox.count() - 1):
                item = self.vbox.itemAt(i)
                if item and item.widget():
                    t = item.widget()
                    if t.show_countdown and t.phase == "active" and t.remaining > toast.remaining:
                        insert_index = i
                        break
        # 无倒计时 toast 始终插入到有倒计时 toast 之后（末尾）

        self.vbox.insertWidget(insert_index, toast)

        # 错峰延迟
        self._stagger_count += 1
        delay = (self._stagger_count - 1) * 60

        def _start_entry_anim():
            # 注：错峰计数在动画完成时递减（见 _on_entry_finished），
            # 不能在启动时递减，否则 processEvents() 提前触发 singleShot(0)
            # 会导致后续 toast 的 delay 计算偏小，错峰失效。
            toast._entering = True
            toast.show()
            toast.setWindowOpacity(0.0)

            end_geo = QtCore.QRect(toast.geometry())
            start_geo = QtCore.QRect(end_geo)
            start_geo.moveLeft(start_geo.left() + toast.width())  # 从右侧滑入

            anim_group = QtCore.QParallelAnimationGroup(toast)

            fade_anim = QtCore.QPropertyAnimation(toast, b"windowOpacity", toast)
            fade_anim.setDuration(200)
            fade_anim.setStartValue(0.0)
            fade_anim.setEndValue(TOAST_OPACITY)
            fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

            slide_anim = QtCore.QPropertyAnimation(toast, b"geometry", toast)
            slide_anim.setDuration(200)
            slide_anim.setStartValue(start_geo)
            slide_anim.setEndValue(end_geo)
            slide_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

            anim_group.addAnimation(fade_anim)
            anim_group.addAnimation(slide_anim)

            # 动画完成时：清除入场标记 + 递减错峰计数
            def _on_entry_finished():
                toast._entering = False
                self._stagger_count -= 1
            anim_group.finished.connect(_on_entry_finished)

            anim_group.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            toast._fade_anim = anim_group

        self.adjust_height()
        QtWidgets.QApplication.processEvents()
        QtCore.QTimer.singleShot(delay, _start_entry_anim)

        # 入场后触发排序（延迟到入场动画启动后）
        QtCore.QTimer.singleShot(delay + 50, self.reorder_toasts)

    def remove_toast(self, toast):
        self.vbox.removeWidget(toast)
        toast.setParent(None)
        self.adjust_height()

    # ========== 倒计时动态排序 ==========
    def reorder_toasts(self):
        # 收集非退出、非入场中的 toast（跳过 stretch）
        toasts = []
        for i in range(self.vbox.count() - 1):
            item = self.vbox.itemAt(i)
            if item and item.widget():
                t = item.widget()
                if not getattr(t, '_exiting', False) and not getattr(t, '_entering', False):
                    toasts.append(t)

        if len(toasts) <= 1:
            return

        # 记录重排前的几何
        old_geos = {id(t): QtCore.QRect(t.geometry()) for t in toasts}

        # 排序
        sorted_toasts = self._sort_toasts(toasts)

        # 检查顺序是否变化
        if sorted_toasts == toasts:
            return

        # 从布局中移除并重新插入
        for t in sorted_toasts:
            self.vbox.removeWidget(t)
        for t in sorted_toasts:
            self.vbox.insertWidget(self.vbox.count() - 1, t)

        QtWidgets.QApplication.processEvents()

        # 对位置变化的 toast 做滑动过渡动画
        for t in sorted_toasts:
            old = old_geos.get(id(t))
            new = t.geometry()
            if old and old != new:
                t.setGeometry(old)  # 先回到旧位置
                anim = QtCore.QPropertyAnimation(t, b"geometry", t)
                anim.setDuration(200)
                anim.setStartValue(old)
                anim.setEndValue(QtCore.QRect(new))
                anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
                anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
                t._reorder_anim = anim

    def _sort_toasts(self, toasts):
        """排序规则：EXPIRED 最上 → ACTIVE 有倒计时(remaining升序) → ACTIVE 无倒计时(插入倒序)"""
        expired = [t for t in toasts if t.phase == "expired"]
        active_cd = [t for t in toasts if t.phase == "active" and t.show_countdown]
        active_no = [t for t in toasts if t.phase == "active" and not t.show_countdown]

        # 已过期：按进入过期阶段的时间升序（最早过期在最上）
        expired.sort(key=lambda t: t.expired_time or 0)

        # 有倒计时：按 remaining 升序，5 秒防抖（差值 < 5 秒保持原序）
        active_cd.sort(key=cmp_to_key(self._compare_countdown))

        # 无倒计时：按插入时间倒序（最新在上）
        active_no.sort(key=lambda t: -getattr(t, '_insert_order', 0))

        return expired + active_cd + active_no

    def _compare_countdown(self, a, b):
        """比较两个有倒计时的 toast，差值 < 5 秒则保持原序"""
        diff = a.remaining - b.remaining
        if abs(diff) >= 5:
            return diff  # remaining 小的排前面
        return 0  # 保持原有相对顺序（stable sort）

    def adjust_height(self):
        """容器高度自适应内容：高度 = min(toolbar + summary + sum_toast_h, 屏幕可用高度)
        高度变化用 150ms QPropertyAnimation 平滑过渡。浮层尺寸同步覆盖 container。"""
        # 1) 懒初始化 QScrollArea
        if not self.scroll:
            self.root.removeWidget(self.container)
            self.scroll = QtWidgets.QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll.setWidget(self.container)
            self.root.addWidget(self.scroll)
            self.scroll.setMinimumWidth(self.width)
            self.scroll.setMaximumWidth(self.width)

            scrollbar_w = self.scroll.verticalScrollBar().sizeHint().width()
            self.scroll.setFixedWidth(self.width + scrollbar_w)
            self.container.setFixedWidth(self.width)
            self._apply_scrollbar_style()

        # 2) 计算各部分高度
        toolbar_h = self.pin_btn.sizeHint().height() + 11  # 上下边距 8+3
        # 摘要行高度（固定 24px，禁用时为 0）
        summary_h = self.summary_row.sizeHint().height() if self.summary_row is not None else 0
        margins_h = 4 + 4 + 3  # root 上下边距 + spacing

        # toast 内容高度之和
        sum_toast_h = 0
        for i in range(self.vbox.count() - 1):  # 跳过末尾 stretch
            item = self.vbox.itemAt(i)
            w = item.widget() if item else None
            if w is not None:
                hint = w.sizeHint().height()
                if hint <= 0:
                    hint = w.height()
                sum_toast_h += hint
        # 加上 vbox 间距
        n_toasts = max(0, self.vbox.count() - 1)
        sum_toast_h += 4 + 6 + n_toasts * 6  # vbox 上下边距 + 间距

        # 3) 容器目标高度 = toolbar + summary + scroll内容 + margins
        target_h = toolbar_h + summary_h + sum_toast_h + margins_h
        # 上限 = 屏幕可用高度 - 2 * margin
        safe_max = self.max_height
        target_h = min(target_h, safe_max)
        target_h = max(target_h, toolbar_h + summary_h + 40)  # 最小高度

        # 4) QScrollArea 高度（不超过内容所需）
        scroll_h = max(40, target_h - toolbar_h - summary_h - margins_h)
        self.scroll.setMinimumHeight(scroll_h)
        self.scroll.setMaximumHeight(scroll_h)

        # 5) 用 QPropertyAnimation 平滑过渡容器几何（150ms）
        x = self.screen.right() - self.width - self.margin
        y = self.screen.top() + self.margin
        target_geo = QtCore.QRect(x, y, self.width, target_h)

        # 终止正在进行的动画（DeleteWhenStopped 可能已删除 C++ 对象）
        if self._height_anim is not None:
            try:
                self._height_anim.stop()
            except RuntimeError:
                pass
            self._height_anim = None

        anim = QtCore.QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(150)
        anim.setStartValue(QtCore.QRect(self.geometry()))
        anim.setEndValue(target_geo)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutCubic)
        # 动画自然结束时清理 Python 引用，避免悬挂指针
        anim.finished.connect(lambda: self._on_height_anim_finished(anim))
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._height_anim = anim

        # 6) 同步浮层尺寸（如果可见）
        if self.overlay is not None and self.overlay.isVisible():
            self._sync_overlay_geometry()

    def _on_height_anim_finished(self, anim):
        """高度动画结束：清理引用，并追加一次浮层位置同步。
        防止动画期间被 refresh_expired_history 等路径调用 _sync_overlay_geometry
        时使用了动画中间值导致浮层位置偏差。"""
        self._clear_height_anim(anim)
        if self.overlay is not None and self.overlay.isVisible():
            self._sync_overlay_geometry()

    def _clear_height_anim(self, anim):
        """动画结束时清理引用，避免访问已删除的 C++ 对象"""
        if self._height_anim is anim:
            self._height_anim = None


# ========== 管理器 ==========
class ToastManager(QtCore.QObject):
    all_closed = QtCore.Signal()

    def __init__(self, theme="dark", no_expired_history=False):
        super().__init__()
        self.toasts = []
        self.theme = theme
        self.no_expired_history = no_expired_history
        # 到期历史记录集合（仅内存维护，不持久化）
        self.expired_history = None if no_expired_history else ExpiredHistory()
        self.container = ToastContainer(theme=theme, no_expired_history=no_expired_history)

    def show_toast(self, title, message, duration=3000, show_countdown=False):
        try:
            toast = Toast(title, message, duration, show_countdown, theme=self.theme)
            toast.closed.connect(self._on_closed)
            toast.remaining_changed.connect(self._on_remaining_changed)
            if not self.no_expired_history:
                toast.expired.connect(self._on_toast_expired)
            self.toasts.append(toast)
            self.container.add_toast(toast)
        except Exception as e:
            print("创建 Toast 出错:", e)

    def _on_closed(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
            self.container.remove_toast(toast)
            if not self.toasts:
                self.all_closed.emit()

    def _on_remaining_changed(self):
        self.container.reorder_toasts()

    def _on_toast_expired(self, toast):
        """Toast 进入 EXPIRED 阶段时记录到历史"""
        if self.no_expired_history or self.expired_history is None:
            return
        rec = ExpiredRecord(
            title=toast.title,
            message=toast.message,
            created_at=toast.created_at,
            expired_at=toast.expired_time or time.time(),
        )
        self.expired_history.add(rec)
        # 刷新面板（如已展开）
        self.container.refresh_expired_history(self.expired_history.all())


# ========== 本地服务端 ==========
class LocalServer(QtCore.QObject):
    message = QtCore.Signal(dict)

    def __init__(self, name="toast_server"):
        super().__init__()
        self.buffer = ""
        self.server = QtNetwork.QLocalServer(self)
        if self.server.isListening():
            self.server.close()
        QtNetwork.QLocalServer.removeServer(name)
        self.server.listen(name)
        self.server.newConnection.connect(self.handle_connection)

    def handle_connection(self):
        socket = self.server.nextPendingConnection()
        socket.readyRead.connect(lambda s=socket: self.read_data(s))

    def read_data(self, socket):
        try:
            self.buffer += socket.readAll().data().decode("utf-8", errors="ignore")
        except Exception as e:
            print("读取数据失败:", e)
            return

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                self.message.emit(payload)
            except Exception as e:
                print(f"解析消息失败: {e}, 内容: {line}")

        socket.disconnectFromServer()


# ========== 客户端发送函数 ==========
def send_message(payload, name="toast_server"):
    socket = QtNetwork.QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(500):
        socket.write((json.dumps(payload) + "\n").encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True
    return False


# ========== 主入口 ==========
def main():
    parser = argparse.ArgumentParser(
        prog="toast",
        description="Toast Notification Program"
    )
    parser.add_argument("title", nargs="?", default=tr("default_title"),
                        help="The title of the toast notification")
    parser.add_argument("message", nargs="?", default=tr("default_message"),
                        help="The message body of the toast")
    parser.add_argument("duration", nargs="?", type=int, default=4000,
                        help="Display time in milliseconds (default: 4000)")

    parser.add_argument("--keep-alive", action="store_true",
                        help="Keep the program running after all toasts are closed")
    parser.add_argument("--show-countdown", action="store_true",
                        help="Show a countdown timer inside each toast")
    parser.add_argument("--theme", choices=["light", "dark"], default="dark",
                        help="Select theme (default: dark)")
    parser.add_argument("--no-expired-history", action="store_true",
                        help="Disable expired history list (no button, no recording)")

    args = parser.parse_args()

    payload = {
        "title": args.title,
        "message": args.message,
        "duration": args.duration,
        "show_countdown": args.show_countdown,
        "theme": args.theme,
    }

    app = QtWidgets.QApplication(sys.argv)

    QtWidgets.QToolTip.setFont(QtGui.QFont("Microsoft YaHei", 9))
    app.setStyleSheet("""
        QToolTip {
            color: white;
            background-color: rgba(50, 50, 50, 220);
            border: 1px solid white;
            font: 10pt "Microsoft YaHei";
        }
    """)

    if send_message(payload):
        return

    mgr = ToastManager(theme=args.theme, no_expired_history=args.no_expired_history)
    srv = LocalServer()
    srv.message.connect(lambda p: mgr.show_toast(
        p.get("title", "Notification"),
        p.get("message", ""),
        p.get("duration", 3000),
        p.get("show_countdown", False)
    ))

    if not args.keep_alive:
        mgr.all_closed.connect(app.quit)

    mgr.show_toast(payload["title"], payload["message"],
                   payload["duration"], payload["show_countdown"])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
