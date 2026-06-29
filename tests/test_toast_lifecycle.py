"""Qt 组件测试：Toast 生命周期 + 信号"""
import pytest
from PySide6 import QtCore
import toast as toast_mod
from toast import Toast


def test_toast_init_default_values(qtbot, frozen_time):
    """phase=active，duration=3000，remaining==duration//1000"""
    t = Toast("title", "msg", duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    assert t.phase == "active"
    assert t.duration == 3000
    assert t.remaining == 3  # 3000 // 1000
    assert t.expired_time is None
    assert t._exiting is False
    assert t._entering is False


def test_toast_countdown_updates_remaining(qtbot, frozen_time):
    """_tick 多次后 remaining 递减"""
    t = Toast("t", "m", duration=3000, show_countdown=True)
    qtbot.addWidget(t)
    assert t.remaining == 3
    t._tick()
    assert t.remaining == 2
    t._tick()
    assert t.remaining == 1


def test_toast_expired_phase_transition(qtbot, frozen_time):
    """_enter_expired_phase 后 phase==expired"""
    t = Toast("t", "m", duration=3000, show_countdown=True)
    qtbot.addWidget(t)
    assert t.phase == "active"
    # 推进到 remaining=0 触发 expired
    t.remaining = 1
    t._tick()  # remaining 减到 0 → 进入 expired
    assert t.phase == "expired"
    assert t.expired_time is not None


def test_toast_expired_signal_emitted(qtbot, frozen_time):
    """进入 expired 阶段时发射 expired 信号"""
    t = Toast("t", "m", duration=3000, show_countdown=True)
    qtbot.addWidget(t)
    with qtbot.waitSignal(t.expired, timeout=2000):
        t._enter_expired_phase()
    assert t.phase == "expired"


def test_toast_exit_anim_emits_closed(qtbot, frozen_time):
    """start_exit_anim 后 closed 信号最终发射"""
    t = Toast("t", "m", duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    t.resize(300, 100)
    t.show()
    qtbot.waitExposed(t)

    # mock _final_close 避免 deleteLater 导致 qtbot teardown 时 widget 已删除
    t._final_close = lambda: t.closed.emit(t)
    with qtbot.waitSignal(t.closed, timeout=5000):
        t.start_exit_anim()
    assert t._exiting is True


def test_toast_manual_close_triggers_exit(qtbot, frozen_time):
    """_manual_close 调用 start_exit_anim，_exiting 标记为 True"""
    t = Toast("t", "m", duration=3000, show_countdown=False)
    qtbot.addWidget(t)
    t.resize(300, 100)
    t.show()
    qtbot.waitExposed(t)

    assert t._exiting is False
    # mock _final_close 阻止 deleteLater（避免 widget 被销毁影响后续断言）
    t._final_close = lambda: t.closed.emit(t)
    t._manual_close()
    assert t._exiting is True


def test_toast_pin_persists_through_expired(qtbot, frozen_time):
    """Toast 本身没有 pin 状态（pin 是 container 的概念）。
    验证 phase 切换不影响 toast 是否进入 expired：所有 toast 都会进入 expired。"""
    t = Toast("t", "m", duration=3000, show_countdown=True)
    qtbot.addWidget(t)
    t.remaining = 1
    t._tick()
    # 即使 pinned 也会进入 expired 阶段（exit 由 container 控制）
    assert t.phase == "expired"


def test_toast_countdown_display_format(qtbot, frozen_time, monkeypatch):
    """_update_countdown 文本格式正确"""
    monkeypatch.setattr(toast_mod, "LANG", "en")
    t = Toast("t", "m", duration=3000, show_countdown=True)
    qtbot.addWidget(t)
    t.remaining = 65  # 1m 5s
    t._update_countdown()
    text = t.countdown_lbl.text()
    assert "1m" in text
    assert "5s" in text
    assert "Remaining" in text


def test_toast_theme_applied(qtbot, frozen_time):
    """theme='light' vs 'dark' 样式不同"""
    t_dark = Toast("t", "m", duration=1000, show_countdown=False, theme="dark")
    t_light = Toast("t", "m", duration=1000, show_countdown=False, theme="light")
    qtbot.addWidget(t_dark)
    qtbot.addWidget(t_light)
    assert t_dark.theme == "dark"
    assert t_light.theme == "light"
    assert t_dark._base_style != t_light._base_style


def test_toast_zero_duration_handling(qtbot, frozen_time):
    """duration=0 不崩溃（边界：remaining=max(1, 0)=1）"""
    t = Toast("t", "m", duration=0, show_countdown=False)
    qtbot.addWidget(t)
    assert t.duration == 0
    assert t.remaining == 1  # max(1, 0 // 1000) = max(1, 0) = 1
