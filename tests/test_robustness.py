"""健壮性测试：异常输入与边界条件

验证程序在异常输入下不崩溃（graceful handling）。
"""
import pytest
from PySide6 import QtCore, QtWidgets
import toast as toast_mod
from toast import Toast, ToastManager, ExpiredHistory, ExpiredRecord


def test_robust_empty_title_message(qtbot, frozen_time):
    """title="" message="" 不崩溃"""
    t = Toast("", "", duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    # 空字符串应回退到默认值（title or tr("default_title")）
    assert t.title == "" or "Default" in t.title or "默认" in t.title
    assert t.message == "" or "test" in t.message.lower() or "测试" in t.message


def test_robust_none_title_raises_or_fallback(qtbot, frozen_time):
    """title=None 应被合理处理（Toast 用 'or' 回退到默认值）"""
    # Toast.__init__ 中 self.title = title or tr("default_title")
    # None 是 falsy，应回退到默认值
    t = Toast(None, None, duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    # title 应是默认值，不是 None
    assert t.title is not None
    assert t.message is not None


def test_robust_super_long_title_10000_chars(qtbot, frozen_time):
    """title=10000 字符不崩溃"""
    long_title = "A" * 10000
    t = Toast(long_title, "m", duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    assert t.title == long_title
    # 显示不崩溃（paintEvent 能处理）
    t.resize(300, 100)
    t.show()
    qtbot.waitExposed(t)


def test_robust_super_long_message_10000_chars(qtbot, frozen_time):
    """message=10000 字符不崩溃"""
    long_msg = "B" * 10000
    t = Toast("t", long_msg, duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    assert t.message == long_msg
    t.resize(300, 100)
    t.show()
    qtbot.waitExposed(t)


def test_robust_negative_duration(qtbot, frozen_time):
    """duration=-1 不崩溃（remaining=max(1, -1//1000)=max(1, -1)=1）"""
    t = Toast("t", "m", duration=-1, show_countdown=True)
    qtbot.addWidget(t)
    # max(1, -1 // 1000) = max(1, -1) = 1
    assert t.remaining == 1


def test_robust_huge_duration(qtbot, frozen_time):
    """duration=86400000（24h）不崩溃"""
    t = Toast("t", "m", duration=86400000, show_countdown=True)
    qtbot.addWidget(t)
    assert t.duration == 86400000
    # remaining = 86400000 // 1000 = 86400 秒 = 24 小时
    assert t.remaining == 86400
    # _update_countdown 应正确显示天
    t._update_countdown()
    text = t.countdown_lbl.text()
    assert "1d" in text or "1天" in text  # 86400 秒 = 1 天


def test_robust_concurrent_add_remove(qtbot, manager, frozen_time):
    """同时 add 和 remove 不竞态崩溃"""
    toasts = []
    for i in range(10):
        manager.show_toast(f"t{i}", "m", duration=60000, show_countdown=True)
        toasts.append(manager.toasts[-1])
    # 交替移除和添加
    for i in range(0, 10, 2):
        t = toasts[i]
        # 直接调用 closed 信号模拟关闭（绕过动画时序）
        t.closed.emit(t)
        qtbot.wait(10)
    # 验证部分已移除
    assert len(manager.toasts) == 5
    # 继续添加
    for i in range(5):
        manager.show_toast(f"new{i}", "m", duration=60000, show_countdown=True)
    assert len(manager.toasts) == 10


def test_robust_resource_leak_after_close(qtbot, manager, frozen_time):
    """关闭 5 个 toast 后 manager.toasts 列表清空，无 Python 异常

    验证修复：add_toast 中 entry_timer/reorder_timer 父子化到 toast，
    toast 被删除时 timer 自动停止，不再触发 _start_entry_anim 访问已删除 C++ 对象。
    """
    created = []
    for i in range(5):
        manager.show_toast(f"t{i}", "m", duration=60000, show_countdown=True)
        created.append(manager.toasts[-1])
    assert len(manager.toasts) == 5
    for t in created:
        t.closed.emit(t)
        qtbot.wait(10)
    assert len(manager.toasts) == 0
    # 让 pending entry timers 完成（父子化后 toast 删除时自动停止）
    qtbot.wait(500)
