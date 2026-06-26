import argparse
import json
import sys
import time

from PySide6 import QtCore, QtWidgets, QtGui, QtNetwork
# ========== 内置多语言支持 ==========
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
}


def tr(key: str) -> str:
    return STRINGS.get(key, {}).get(LANG, key)


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


# ========== 单个通知 ==========
class Toast(QtWidgets.QFrame):
    closed = QtCore.Signal(object)

    def __init__(self, title, message, duration=3000, show_countdown=False, theme="dark"):
        super().__init__()
        self.setObjectName("toast")
        self.duration = duration
        self.remaining = max(1, duration // 1000)
        self.show_countdown = show_countdown
        self._fade_anim = None
        # 右滑关闭手势状态（Windows 平板触摸适配）
        self._drag = None
        self._slide_back_anim = None
        self._swipe_threshold = 0.5      # 松手时位移需达到卡片宽度的 50%
        self._fling_velocity = 600.0    # px/s，快速右滑判定阈值

        # 主题样式搭配（字体 12pt → 10pt，圆角 12px → 10px）
        if theme == "light":
            style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(255,255,255,220), stop:1 rgba(240,240,240,180));
                    border-radius: 10px;
                    border: 1px solid rgba(0,0,0,40);
                }
                QLabel { color: black; font-size: 10pt; background: transparent; }
            """
            countdown_color = "blue"
        else:
            style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(40,40,40,220), stop:1 rgba(20,20,20,180));
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,40);
                }
                QLabel { color: white; font-size: 10pt; background: transparent; }
            """
            countdown_color = "yellow"

        self.setStyleSheet(style)

        # 阴影（blur 30→20, offset 6→4 等比缩减）
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        # 布局（margins 12,8,12,12 → 8,5,8,8，spacing 6→4）
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

        # 自动关闭
        QtCore.QTimer.singleShot(self.duration, self.fade_out)

        # 倒计时更新
        if self.show_countdown:
            self._update_countdown()
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(1000)

    def showEvent(self, event):
        super().showEvent(event)
        # 稳定淡入（持有引用，避免被回收），目标为 TOAST_OPACITY
        self.setWindowOpacity(0)
        self._fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0)
        self._fade_anim.setEndValue(TOAST_OPACITY)
        self._fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0 and hasattr(self, "_timer"):
            self._timer.stop()
        self._update_countdown()

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

    def _manual_close(self):
        self.fade_out()

    def fade_out(self):
        self._fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(TOAST_OPACITY)
        self._fade_anim.setEndValue(0)
        self._fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(self._final_close)
        self._fade_anim.start()

    def _final_close(self):
        self.closed.emit(self)
        self.deleteLater()

    # ========== 右滑关闭手势（触摸跟手） ==========
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._drag is None:
            gp = event.globalPosition().toPoint()
            self._drag = {
                "start_global": gp,
                "origin_geo": self.geometry(),
                "last_x": gp.x(),
                "last_time": time.perf_counter(),
                "velocity": 0.0,
                "moved": False,
            }
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag:
            gp = event.globalPosition().toPoint()
            delta = gp - self._drag["start_global"]
            # 仅向右跟手（左滑钳制为 0），垂直保持不变
            dx = max(0, delta.x())
            if dx > 2:
                self._drag["moved"] = True
            self.setGeometry(self._drag["origin_geo"].translated(dx, 0))
            # 瞬时速度（px/s），指数平滑去抖
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
            origin_x = self._drag["origin_geo"].x()
            offset = self.geometry().x() - origin_x
            velocity = self._drag["velocity"]
            width = self.width() or 1
            # 达到位移阈值，或快速右滑（fling）即触发关闭
            if offset >= width * self._swipe_threshold or velocity >= self._fling_velocity:
                self._drag = None
                self.fade_out()
                return
            # 否则回弹到原位
            self._animate_back_to(self._drag["origin_geo"])
            self._drag = None
            return
        self._drag = None
        super().mouseReleaseEvent(event)

    def _animate_back_to(self, geo):
        self._slide_back_anim = QtCore.QPropertyAnimation(self, b"geometry", self)
        self._slide_back_anim.setDuration(200)
        self._slide_back_anim.setStartValue(self.geometry())
        self._slide_back_anim.setEndValue(geo)
        self._slide_back_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._slide_back_anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


# ========== 容器 ==========
class ToastContainer(QtWidgets.QWidget):
    def __init__(self, theme="dark"):
        super().__init__(None, QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint |
                         QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.theme = theme
        self.pinned = True
        self.margin = 50
        self.screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.max_height = self.screen.height() - 2 * self.margin
        self.width = 300  # 380 → 300

        # 初始位置（靠右上）
        init_h = 120

        self.setGeometry(
            self.screen.right() - self.width - self.margin,
            self.screen.top() + self.margin,
            self.width,
            init_h
        )

        # 顶部工具栏（margins 6,6,6,4 → 4,4,4,3，spacing 6→4）
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

        # 先创建 container（margins 8,6,8,8 → 6,4,6,6，spacing 10→6）
        self.container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(6, 4, 6, 6)
        self.vbox.setSpacing(6)
        self.vbox.addStretch()

        # 再创建 root 布局（margins 6,6,6,6 → 4,4,4,4，spacing 4→3）
        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(4, 4, 4, 4)
        self.root.setSpacing(3)
        self.root.addLayout(toolbar)
        self.root.addWidget(self.container)

        self.scroll = None  # 超出时才启用
        self.setStyleSheet("background: transparent; border-radius: 10px;")

        self.show()
        # 统一半透明
        self.setWindowOpacity(TOAST_OPACITY)

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
        # setWindowFlags 后 opacity 会重置，需重新设置
        self.setWindowOpacity(TOAST_OPACITY)

    def add_toast(self, toast):
        # 插入布局
        self.vbox.insertWidget(self.vbox.count() - 1, toast)

        # 先不立即 show，而是延迟到布局稳定后再 show
        def _start_animation():
            toast.show()
            toast.setWindowOpacity(0.0)

            start_geo = toast.geometry()
            end_geo = toast.geometry()
            start_geo.moveTop(start_geo.top() - 20)

            anim_group = QtCore.QParallelAnimationGroup(toast)

            fade_anim = QtCore.QPropertyAnimation(toast, b"windowOpacity", toast)
            fade_anim.setDuration(250)
            fade_anim.setStartValue(0.0)
            fade_anim.setEndValue(TOAST_OPACITY)
            fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

            slide_anim = QtCore.QPropertyAnimation(toast, b"geometry", toast)
            slide_anim.setDuration(250)
            slide_anim.setStartValue(start_geo)
            slide_anim.setEndValue(end_geo)
            slide_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

            anim_group.addAnimation(fade_anim)
            anim_group.addAnimation(slide_anim)
            anim_group.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        # 先调整容器高度，确保滚动条状态正确
        self.adjust_height()

        # 延迟到下一个事件循环再启动动画，避免重叠
        QtWidgets.QApplication.processEvents()  # 强制刷新布局
        QtCore.QTimer.singleShot(0, _start_animation)

    def remove_toast(self, toast):
        self.vbox.removeWidget(toast)
        toast.setParent(None)
        self.adjust_height()

    def adjust_height(self):
        # 固定容器高度，不再随内容动态变化
        safe_max = self.max_height - 20
        fixed_height = safe_max

        # 固定顶边位置（右上角）
        x = self.screen.right() - self.width - self.margin
        y = self.screen.top() + self.margin

        # 直接固定容器大小和位置
        self.resize(self.width, fixed_height)
        self.move(x, y)

        # 始终使用滚动区域来容纳 toast
        if not self.scroll:
            self.root.removeWidget(self.container)
            self.scroll = QtWidgets.QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll.setWidget(self.container)
            self.root.addWidget(self.scroll)
            # 强制 scroll 匹配容器宽度
            self.scroll.setMinimumWidth(self.width)
            self.scroll.setMaximumWidth(self.width)

            scrollbar_w = self.scroll.verticalScrollBar().sizeHint().width()
            self.scroll.setFixedWidth(self.width + scrollbar_w)
            self.container.setFixedWidth(self.width)

        # 工具栏高度（按钮更小，余量 12→8）
        toolbar_h = self.pin_btn.sizeHint().height() + 8
        self.scroll.setMinimumHeight(fixed_height - toolbar_h)
        self.scroll.setMaximumHeight(fixed_height - toolbar_h)


# ========== 管理器 ==========
class ToastManager(QtCore.QObject):
    all_closed = QtCore.Signal()

    def __init__(self, theme="dark"):
        super().__init__()
        self.toasts = []
        self.theme = theme
        self.container = ToastContainer(theme=theme)

    def show_toast(self, title, message, duration=3000, show_countdown=False):
        try:
            toast = Toast(title, message, duration, show_countdown, theme=self.theme)
            toast.closed.connect(self._on_closed)
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

    args = parser.parse_args()

    # 构造 payload
    payload = {
        "title": args.title,
        "message": args.message,
        "duration": args.duration,
        "show_countdown": args.show_countdown,
        "theme": args.theme,
    }

    # 如已有实例 → 发消息后退出
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

    # 新实例作为服务端
    mgr = ToastManager(theme=args.theme)
    srv = LocalServer()
    srv.message.connect(lambda p: mgr.show_toast(
        p.get("title", "Notification"),
        p.get("message", ""),
        p.get("duration", 3000),
        p.get("show_countdown", False)
    ))

    if not args.keep_alive:
        mgr.all_closed.connect(app.quit)

    # 启动时至少显示一个 toast
    mgr.show_toast(payload["title"], payload["message"],
                   payload["duration"], payload["show_countdown"])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
