"""管理器测试：ToastManager 流程

注：start_exit_anim 启动动画后由 _final_close 发射 closed 信号，
动画在 offscreen 平台可能时序不稳定，因此测试中直接调用 _final_close
模拟动画结束，避免 waitSignal 超时。"""
import pytest
from PySide6 import QtCore
import toast as toast_mod
from toast import ToastManager, Toast


def test_manager_show_toast_creates_instance(qtbot, manager, frozen_time):
    """show_toast 后 toasts 长度==1"""
    assert len(manager.toasts) == 0
    manager.show_toast("title", "msg", duration=3000, show_countdown=True)
    assert len(manager.toasts) == 1


def test_manager_all_closed_signal(qtbot, manager, frozen_time):
    """单个 toast 关闭后 all_closed 信号 + toasts 清空"""
    manager.show_toast("t", "m", duration=3000, show_countdown=True)
    assert len(manager.toasts) == 1
    toast = manager.toasts[0]

    received = []
    manager.all_closed.connect(lambda: received.append(True))
    # 直接调用 closed 信号模拟动画结束（绕过 _final_close 的 deleteLater 副作用）
    toast.closed.emit(toast)
    qtbot.wait(50)
    assert len(manager.toasts) == 0
    assert received == [True]


def test_manager_multiple_toasts_all_closed(qtbot, manager, frozen_time):
    """3 个 toast 全部关闭后 all_closed 仅触发一次"""
    for i in range(3):
        manager.show_toast(f"t{i}", "m", duration=60000, show_countdown=True)
    assert len(manager.toasts) == 3

    received = []
    manager.all_closed.connect(lambda: received.append(True))
    for toast in list(manager.toasts):
        toast.closed.emit(toast)
        qtbot.wait(20)
    assert len(manager.toasts) == 0
    assert len(received) == 1


def test_manager_expired_history_recorded(qtbot, manager_with_history, frozen_time):
    """toast 过期后 expired_history.count()==1"""
    assert manager_with_history.expired_history is not None
    assert manager_with_history.expired_history.count() == 0
    manager_with_history.show_toast("t", "m", duration=3000, show_countdown=True)
    toast = manager_with_history.toasts[0]
    toast._enter_expired_phase()
    assert manager_with_history.expired_history.count() == 1


def test_manager_no_expired_history_mode(qtbot, manager, frozen_time):
    """no_expired_history=True 时不记录"""
    assert manager.expired_history is None
    manager.show_toast("t", "m", duration=3000, show_countdown=True)
    toast = manager.toasts[0]
    toast._enter_expired_phase()
    assert manager.expired_history is None  # 仍未创建
