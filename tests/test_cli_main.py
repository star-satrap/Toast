"""CLI 测试：main() argparse + 启动路径

main() 创建新 QApplication，与 pytest-qt 单例冲突。
通过 monkeypatch QApplication 构造返回现有 qapp 解决。
"""
import sys
import pytest
from unittest.mock import MagicMock
import toast as toast_mod


def _patch_qapp(monkeypatch, qapp):
    """让 main() 中 QtWidgets.QApplication(...) 返回现有 qapp。
    FakeQApp 必须提供 instance()/primaryScreen()/quit()/processEvents() 静态方法，
    pytest-qt teardown、ToastContainer 初始化、add_toast 都会调用。"""
    from PySide6 import QtCore
    from unittest.mock import MagicMock
    screen = MagicMock()
    screen.availableGeometry.return_value = QtCore.QRect(0, 0, 1920, 1080)

    class FakeQApp:
        def __new__(cls, *args, **kwargs):
            return qapp
        @staticmethod
        def instance():
            return qapp
        @staticmethod
        def primaryScreen():
            return screen
        @staticmethod
        def quit(*args, **kwargs):
            return qapp.quit(*args, **kwargs)
        @staticmethod
        def processEvents(*args, **kwargs):
            return qapp.processEvents(*args, **kwargs)
    monkeypatch.setattr(toast_mod.QtWidgets, "QApplication", FakeQApp)


def test_main_default_args(monkeypatch, qapp):
    """无参数时 title/message/duration 用默认值，send_message 成功直接 return"""
    _patch_qapp(monkeypatch, qapp)
    monkeypatch.setattr(toast_mod, "LANG", "en")  # 固定英文避免系统语言干扰
    captured = {}

    def fake_send_message(payload, name="toast_server"):
        captured["payload"] = payload
        return True

    monkeypatch.setattr(toast_mod, "send_message", fake_send_message)
    monkeypatch.setattr(sys, "argv", ["toast"])

    toast_mod.main()

    assert captured["payload"]["title"] == "Default Notification"
    assert captured["payload"]["message"] == "This is a test message"
    assert captured["payload"]["duration"] == 4000
    assert captured["payload"]["theme"] == "dark"
    assert captured["payload"]["show_countdown"] is False


def test_main_custom_args(monkeypatch, qapp):
    """自定义 title/message/duration/--theme/--no-expired-history"""
    _patch_qapp(monkeypatch, qapp)
    captured = {}

    def fake_send_message(payload, name="toast_server"):
        captured["payload"] = payload
        return True

    monkeypatch.setattr(toast_mod, "send_message", fake_send_message)
    monkeypatch.setattr(sys, "argv", [
        "toast", "Custom Title", "Custom Message", "5000",
        "--show-countdown", "--theme", "light", "--no-expired-history"
    ])

    toast_mod.main()

    assert captured["payload"]["title"] == "Custom Title"
    assert captured["payload"]["message"] == "Custom Message"
    assert captured["payload"]["duration"] == 5000
    assert captured["payload"]["show_countdown"] is True
    assert captured["payload"]["theme"] == "light"


def test_main_send_message_success_path(monkeypatch, qapp):
    """send_message 返回 True 时直接 return，不启动 ToastManager"""
    _patch_qapp(monkeypatch, qapp)
    manager_created = []

    monkeypatch.setattr(toast_mod, "send_message", lambda *a, **kw: True)

    original_init = toast_mod.ToastManager.__init__
    def spy_init(self, *args, **kwargs):
        manager_created.append(True)
        return original_init(self, *args, **kwargs)
    monkeypatch.setattr(toast_mod.ToastManager, "__init__", spy_init)

    monkeypatch.setattr(sys, "argv", ["toast"])

    toast_mod.main()
    assert len(manager_created) == 0  # ToastManager 不应被实例化


def test_main_server_path_launches_app(monkeypatch, qapp):
    """send_message 返回 False 时启动 ToastManager（mock app.exec 立即返回）"""
    _patch_qapp(monkeypatch, qapp)
    monkeypatch.setattr(toast_mod, "send_message", lambda *a, **kw: False)
    monkeypatch.setattr(sys, "argv", ["toast", "T", "M", "1000"])

    exit_called = []
    monkeypatch.setattr(toast_mod.sys, "exit", lambda code=0: exit_called.append(code))

    # mock app.exec 立即返回 0
    monkeypatch.setattr(qapp, "exec", lambda: 0)

    # mock LocalServer 避免真实 socket
    class FakeServer:
        def __init__(self, *a, **kw):
            self.message = MagicMock()
        def close(self): pass
    monkeypatch.setattr(toast_mod, "LocalServer", FakeServer)

    toast_mod.main()
    assert len(exit_called) == 1
