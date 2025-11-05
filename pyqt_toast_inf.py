import argparse
import json
import sys

from PySide6 import QtCore, QtWidgets, QtNetwork
from pyqttoast import Toast, ToastPreset, ToastPosition

# ========== 多语言支持 ==========
LANG = "en"
STRINGS = {
    "default_title": {"en": "Default Notification", "zh": "默认通知"},
    "default_message": {"en": "This is a test message", "zh": "这是一个测试消息"},
    "countdown_prefix": {"en": "Remaining: ", "zh": "剩余时间："},
    "seconds": {"en": "s", "zh": "秒"},
}


def tr(key): return STRINGS.get(key, {}).get(LANG, key)


# ========== 本地服务端 ==========
class LocalServer(QtCore.QObject):
    message = QtCore.Signal(dict)

    def __init__(self, name="toast_server"):
        super().__init__()
        self.buffer = ""
        self.server = QtNetwork.QLocalServer(self)
        QtNetwork.QLocalServer.removeServer(name)
        self.server.listen(name)
        self.server.newConnection.connect(self.handle_connection)

    def handle_connection(self):
        socket = self.server.nextPendingConnection()
        socket.readyRead.connect(lambda s=socket: self.read_data(s))

    def read_data(self, socket):
        self.buffer += socket.readAll().data().decode("utf-8", errors="ignore")
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                self.message.emit(payload)
            except Exception as e:
                print("解析失败:", e)
        socket.disconnectFromServer()


# ========== 客户端发送 ==========
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


# ========== Toast 显示（倒计时 + 进度条 + 主题切换） ==========
def show_toast(payload):
    toast = Toast()
    toast.setTitle(payload.get("title", tr("default_title")))
    base_msg = payload.get("message", tr("default_message"))
    duration = payload.get("duration", 4000)
    toast.setDuration(duration)

    # 主题切换 + 样式
    theme = payload.get("theme", "dark").lower()
    if theme == "success":
        toast.applyPreset(ToastPreset.SUCCESS)
        countdown_color = "green"
        bar_color = "#32CD32"
    elif theme == "error":
        toast.applyPreset(ToastPreset.ERROR)
        countdown_color = "red"
        bar_color = "#FF4500"
    elif theme == "warning":
        toast.applyPreset(ToastPreset.WARNING)
        countdown_color = "orange"
        bar_color = "#FFA500"
    elif theme == "light":
        toast.applyPreset(ToastPreset.INFORMATION)
        toast.setStyleSheet("""
            QLabel { color: black; }
            QWidget { background-color: rgba(255,255,255,230); border-radius: 8px; }
        """)
        countdown_color = "blue"
        bar_color = "#0078D7"
    else:  # 默认 dark/info
        toast.applyPreset(ToastPreset.INFORMATION)
        toast.setStyleSheet("""
            QLabel { color: white; }
            QWidget { background-color: rgba(40,40,40,230); border-radius: 8px; }
        """)
        countdown_color = "yellow"
        bar_color = "#FFD700"

    # 倒计时 + 进度条
    if payload.get("show_countdown", False):
        remaining = duration // 1000

        # 倒计时标签
        countdown_lbl = QtWidgets.QLabel(toast)
        countdown_lbl.setStyleSheet(f"color: {countdown_color}; font-weight: bold;")
        toast.layout().addWidget(countdown_lbl)

        # 进度条
        progress = QtWidgets.QProgressBar(toast)
        progress.setRange(0, remaining)
        progress.setValue(remaining)
        progress.setTextVisible(True)
        progress.setFixedHeight(6)
        progress.setStyleSheet(f"QProgressBar::chunk {{ background-color: {bar_color}; }}")
        toast.layout().addWidget(progress)

        timer = QtCore.QTimer(toast)

        def update():
            nonlocal remaining
            if remaining <= 0:
                timer.stop()
                return
            countdown_lbl.setText(f"{tr('countdown_prefix')}{remaining}{tr('seconds')}")
            progress.setValue(remaining)
            remaining -= 1

        timer.timeout.connect(update)
        timer.start(1000)
        update()
    else:
        toast.setText(base_msg)

    toast.show()


# ========== 主入口 ==========
def main():
    parser = argparse.ArgumentParser(description="Toast Notification Program")
    parser.add_argument("title", nargs="?", default=tr("default_title"))
    parser.add_argument("message", nargs="?", default=tr("default_message"))
    parser.add_argument("duration", nargs="?", type=int, default=4000)
    parser.add_argument("--theme", choices=["info", "success", "warning", "error", "light", "dark"], default="dark")
    parser.add_argument("--show-countdown", action="store_true")
    args = parser.parse_args()

    payload = {
        "title": args.title,
        "message": args.message,
        "duration": args.duration,
        "theme": args.theme,
        "show_countdown": args.show_countdown,
    }

    app = QtWidgets.QApplication(sys.argv)

    # 全局配置
    Toast.setPosition(ToastPosition.TOP_RIGHT)
    Toast.setMaximumOnScreen(5)
    Toast.setSpacing(12)
    Toast.setOffset(30, 50)

    # 如果已有实例 → 发消息后退出
    if send_message(payload):
        return

    # 新实例作为服务端
    srv = LocalServer()
    srv.message.connect(show_toast)

    # 启动时至少显示一个
    show_toast(payload)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
