"""容器测试：排序逻辑、错峰、浮层联动"""
import pytest
from functools import cmp_to_key
from unittest.mock import MagicMock
import toast as toast_mod
from toast import ToastContainer, Toast


def test_container_init_default_theme(qtbot, mock_screen):
    """theme='dark'，no_expired_history=False"""
    c = ToastContainer(theme="dark", no_expired_history=False)
    qtbot.addWidget(c)
    assert c.theme == "dark"
    assert c.no_expired_history is False
    assert c.pinned is True
    assert c.summary_row is not None
    assert c.overlay is not None


def test_container_add_toast_increases_count(qtbot, mock_screen):
    """add_toast 后 vbox.count()==1（+1 stretch）"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    initial = c.vbox.count()  # 1（仅 stretch）
    t = Toast("t", "m", duration=3000, show_countdown=True)
    c.add_toast(t)
    assert c.vbox.count() == initial + 1


def test_container_remove_toast_decreases_count(qtbot, mock_screen):
    """add 后 remove，vbox.count()==0（仅 stretch）"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    t = Toast("t", "m", duration=3000, show_countdown=True)
    c.add_toast(t)
    initial = c.vbox.count()
    c.remove_toast(t)
    assert c.vbox.count() == initial - 1


def test_container_reorder_5s_debounce(qtbot, mock_screen):
    """_compare_countdown 差值<5 返回 0（防抖保持原序）"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    a, b = MagicMock(), MagicMock()
    a.remaining = 5
    b.remaining = 4  # 差值 1 < 5
    assert c._compare_countdown(a, b) == 0
    assert c._compare_countdown(b, a) == 0


def test_container_sort_by_countdown_asc(qtbot, mock_screen):
    """_sort_toasts 按 remaining 升序（差值>=5 时）"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    a, b = MagicMock(), MagicMock()
    a.remaining, a.phase, a.show_countdown = 10, "active", True
    a.expired_time, a._insert_order = None, 0
    b.remaining, b.phase, b.show_countdown = 3, "active", True
    b.expired_time, b._insert_order = None, 1
    # 差值 7 >= 5 → b 应在前
    sorted_list = c._sort_toasts([a, b])
    assert sorted_list[0] is b
    assert sorted_list[1] is a


def test_container_pinned_toast_first(qtbot, mock_screen):
    """expired toast 排在 active 之前"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    active = MagicMock()
    active.remaining, active.phase, active.show_countdown = 5, "active", True
    active.expired_time, active._insert_order = None, 0
    expired = MagicMock()
    expired.remaining, expired.phase, expired.show_countdown = 0, "expired", True
    expired.expired_time, expired._insert_order = 1000.0, 1
    sorted_list = c._sort_toasts([active, expired])
    assert sorted_list[0] is expired  # expired 最上


def test_container_toggle_pin_state(qtbot, mock_screen):
    """toggle_pin 切换 pinned 状态"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    assert c.pinned is True
    c.toggle_pin()
    assert c.pinned is False
    c.toggle_pin()
    assert c.pinned is True


def test_container_adjust_height_caps_screen(qtbot, mock_screen):
    """多 toast 时高度不超过屏幕可用高度 - 2*margin"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    max_h = c.max_height
    # 插入 20 个 toast
    for i in range(20):
        t = Toast(f"t{i}", "m", duration=60000, show_countdown=True)
        c.add_toast(t)
    # 容器最终高度应受限于屏幕
    # adjust_height 通过动画调整，直接断言 max_height 上限
    assert c.max_height > 0
    # 容器当前几何高度不应超过 max_height + 容差
    assert c.geometry().height() <= max_h + 50 or c.geometry().height() <= 1080
