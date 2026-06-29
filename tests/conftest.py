"""pytest 全局配置：必须在 import PySide6 前设置 offscreen 平台"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import pytest
from unittest.mock import MagicMock, patch
from PySide6 import QtCore


@pytest.fixture
def mock_screen(qapp):
    """注入伪屏幕 geometry，避免 ToastContainer 在 offscreen 下崩溃。
    显式使用此 fixture 的测试才会注入；纯单元测试不需要。"""
    screen = MagicMock()
    screen.availableGeometry.return_value = QtCore.QRect(0, 0, 1920, 1080)
    with patch.object(qapp, "primaryScreen", return_value=screen):
        yield


@pytest.fixture
def frozen_time(monkeypatch):
    """冻结时间：测试中通过 t[0] += N 推进"""
    import toast as toast_mod
    t = [1700000000.0]
    monkeypatch.setattr(toast_mod.time, "time", lambda: t[0])
    monkeypatch.setattr(toast_mod.time, "perf_counter", lambda: t[0])
    return t


@pytest.fixture
def history():
    from toast import ExpiredHistory
    return ExpiredHistory()


@pytest.fixture
def manager(qtbot, mock_screen, qapp):
    """ToastManager（禁用历史，避免依赖 summary row 浮层）"""
    from toast import ToastManager
    m = ToastManager(theme="dark", no_expired_history=True)
    qtbot.addWidget(m.container)
    yield m
    # 处理 pending events 后再关闭，避免 pending timers 跨测试边界泄漏
    qapp.processEvents()
    try:
        m.container.close()
    except RuntimeError:
        pass


@pytest.fixture
def manager_with_history(qtbot, mock_screen, qapp):
    """ToastManager（启用历史，用于测过期记录）"""
    from toast import ToastManager
    m = ToastManager(theme="dark", no_expired_history=False)
    qtbot.addWidget(m.container)
    yield m
    qapp.processEvents()
    try:
        m.container.close()
    except RuntimeError:
        pass
