import argparse
import json
import sys

from PySide6 import QtCore, QtWidgets, QtGui, QtNetwork
# ========== 内置多语言支持 ==========
from PySide6.QtCore import QLocale

# pyside6 版本： pip install pyside6==6.7.3 | 6.7.3版本适用于Windows Server 2016
# 部署命令 pyside6-deploy .\toast.py

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

        # 主题样式搭配
        if theme == "light":
            style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(255,255,255,220), stop:1 rgba(240,240,240,180));
                    border-radius: 12px;
                    border: 1px solid rgba(0,0,0,40);
                }
                QLabel { color: black; font-size: 12pt; background: transparent; }
            """
            countdown_color = "blue"
        else:
            style = """
                #toast {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(40,40,40,220), stop:1 rgba(20,20,20,180));
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,40);
                }
                QLabel { color: white; font-size: 12pt; background: transparent; }
            """
            countdown_color = "yellow"

        self.setStyleSheet(style)

        # 阴影
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        # 布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        # 标题 + 关闭
        top_layout = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel(f"<b>{title or tr('default_title')}</b>")
        close_btn = QtWidgets.QToolButton()
        close_btn.setText("×")
        close_btn.setMinimumSize(28, 28)
        if theme == "light":
            close_btn.setStyleSheet("""
                QToolButton {
                    font-weight: bold;
                    font-size: 16pt;
                    /* default: no border, but keep space for radius */
                    border: 2px solid transparent;
                    border-radius: 6px;
                    color: black;
                    padding: 2px;              /* slightly tighter for icon */
                    background: transparent;
                }
                QToolButton:hover {
                    /* hover: bright blue edge + subtle blue wash */
                    border: 2px solid #00BFFF;
                    background: rgba(0, 191, 255, 30);
                    color: red;                /* keep your existing red hover color */
                }
                QToolButton:pressed {
                    /* pressed: orange edge + stronger wash */
                    border: 2px solid #FF4500;
                    background: rgba(255, 69, 0, 50);
                    color: red;
                }
            """)
        else:
            close_btn.setStyleSheet("""
                QToolButton {
                    font-weight: bold;
                    font-size: 16pt;
                    border: 2px solid transparent;
                    border-radius: 6px;
                    color: white;
                    padding: 2px;
                    background: transparent;
                }
                QToolButton:hover {
                    border: 2px solid #00BFFF;
                    background: rgba(0, 191, 255, 40);  /* slightly stronger for dark bg */
                    color: red;
                }
                QToolButton:pressed {
                    border: 2px solid #FF4500;
                    background: rgba(255, 69, 0, 60);
                    color: red;
                }
            """)

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
            f"color: {countdown_color}; font-weight: bold; background: transparent;"
        )
        layout.addWidget(self.countdown_lbl)

        # 最小尺寸设置：只固定宽度，高度交给布局自适应
        # self.setMinimumWidth(320)
        # self.setSizePolicy(
        #     QtWidgets.QSizePolicy.Preferred,
        #     QtWidgets.QSizePolicy.MinimumExpanding
        # )

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
        # 稳定淡入（持有引用，避免被回收）
        self.setWindowOpacity(0)
        self._fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0)
        self._fade_anim.setEndValue(1)
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
        self._fade_anim.setStartValue(1)
        self._fade_anim.setEndValue(0)
        self._fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(self._final_close)
        self._fade_anim.start()

    def _final_close(self):
        self.closed.emit(self)
        self.deleteLater()


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
        self.width = 380

        # 初始位置（靠右上）
        init_h = 140

        self.setGeometry(
            self.screen.right() - self.width - self.margin,
            self.screen.top() + self.margin,
            self.width,
            init_h
        )

        # 顶部工具栏
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(6, 6, 6, 4)
        toolbar.setSpacing(6)

        self.pin_btn = self.ToolButton()
        self.pin_btn.setText("📌")
        self.pin_btn.setMinimumSize(28, 28)
        self.pin_btn.setToolTip(tr("pin_tooltip_pin"))
        self.pin_btn.clicked.connect(self.toggle_pin)

        self.close_all_btn = self.ToolButton()
        self.close_all_btn.setText("❌")
        self.close_all_btn.setMinimumSize(28, 28)
        self.close_all_btn.setToolTip(tr("close_all_tooltip"))
        self.close_all_btn.clicked.connect(QtWidgets.QApplication.quit)

        toolbar.addWidget(self.pin_btn)
        toolbar.addWidget(self.close_all_btn)
        toolbar.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        # 先创建 container
        self.container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(8, 6, 8, 8)
        self.vbox.setSpacing(10)
        self.vbox.addStretch()

        # 再创建 root 布局
        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(6, 6, 6, 6)
        self.root.setSpacing(4)
        self.root.addLayout(toolbar)
        self.root.addWidget(self.container)

        self.scroll = None  # 超出时才启用
        self.setStyleSheet("background: transparent; border-radius: 12px;")

        # 初始化样式
        self._apply_toolbar_style()
        self.show()

    def toggle_pin(self):
        self.pinned = not self.pinned
        flags = QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint
        if self.pinned:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
            self.pin_btn.setText("📌")
            self.pin_btn.setToolTip(tr("pin_tooltip_pin"))
        else:
            self.pin_btn.setText("📍")
            self.pin_btn.setToolTip(tr("pin_tooltip_unpin"))
        self.setWindowFlags(flags)
        self.show()

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
            fade_anim.setEndValue(1.0)
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
            # 🔑 强制 scroll 匹配容器宽度
            self.scroll.setMinimumWidth(self.width)
            self.scroll.setMaximumWidth(self.width)

            scrollbar_w = self.scroll.verticalScrollBar().sizeHint().width()
            self.scroll.setFixedWidth(self.width + scrollbar_w)
            self.container.setFixedWidth(self.width)

        # 工具栏高度
        toolbar_h = self.pin_btn.sizeHint().height() + 12
        self.scroll.setMinimumHeight(fixed_height - toolbar_h)
        self.scroll.setMaximumHeight(fixed_height - toolbar_h)

    def _apply_toolbar_style(self):
        if self.theme == "light":
            base_color = "black"
        else:
            base_color = "white"

        btn_style = f"""
            QToolButton {{
                font-weight: bold;
                font-size: 14pt;
                border: 2px solid transparent;   /* 默认透明边框 */
                border-radius: 6px;
                color: {base_color};
                padding: 4px;
            }}
            QToolButton:hover {{
                border: 2px solid #00BFFF;       /* 悬停时亮蓝色边框 */
                background: rgba(0, 191, 255, 30);
            }}
            QToolButton:pressed {{
                border: 2px solid #FF4500;       /* 按下时橙色边框 */
                background: rgba(255, 69, 0, 40);
            }}
        """
        self.pin_btn.setStyleSheet(btn_style)
        self.close_all_btn.setStyleSheet(btn_style)

    class ToolButton(QtWidgets.QToolButton):
        def enterEvent(self, event):
            if self.toolTip():
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self)
            super().enterEvent(event)


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
            color: white;                /* 文字颜色 */
            background-color: rgba(50, 50, 50, 220);  /* 背景色 */
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
