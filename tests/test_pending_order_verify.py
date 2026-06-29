"""验证 _pending_records 与 _records 的顺序关系

本测试证明：
1. _records 是显示顺序（reversed，最新在最上方）
2. _pending_records 是源数据顺序（与 refresh_expired_history 接收的一致）
3. 通过 dirty flag 路径（不可见 → show_overlay）后，显示顺序依然正确

回应误报："_pending_records 顺序与 _records 不一致是 bug"
事实：二者刻意保持不同顺序，因为 set_records 每次都会 reverse 输入。
若改 _pending_records = _records.copy()，下次 set_records 会再次 reverse，导致顺序错乱。
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets
from toast import ExpiredOverlay, ExpiredRecord, ToastManager


def _make_records():
    """生成 3 条记录：r1=最早, r2, r3=最新（按时间顺序）"""
    return [
        ExpiredRecord("oldest", "msg1", 1000.0, 2000.0),  # r1
        ExpiredRecord("middle", "msg2", 2000.0, 3000.0),   # r2
        ExpiredRecord("newest", "msg3", 3000.0, 4000.0),    # r3
    ]


def test_records_and_pending_have_different_orders(qtbot):
    """_records 与 _pending_records 故意保持不同顺序

    _records = reversed (显示顺序，最新在前)
    _pending_records = 原始顺序 (源数据顺序，最早在前)
    """
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)

    records = _make_records()  # [oldest, middle, newest]
    overlay.set_records(records)

    # _records 应是反向（最新在前，用于显示）
    assert overlay._records[0].title == "newest"
    assert overlay._records[1].title == "middle"
    assert overlay._records[2].title == "oldest"

    # _pending_records 应是原始顺序（最早在前，作为下次 set_records 的缓存）
    assert overlay._pending_records[0].title == "oldest"
    assert overlay._pending_records[1].title == "middle"
    assert overlay._pending_records[2].title == "newest"


def test_dirty_flag_path_preserves_display_order(qtbot):
    """dirty flag 路径：refresh_expired_history(隐藏) → show_overlay → 显示顺序正确

    这是误报中提到的场景：从 _pending_records 重建 UI。
    验证：set_records(_pending_records) 后显示顺序仍是 最新在前。
    """
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)

    records = _make_records()  # [oldest, middle, newest]

    # 模拟 refresh_expired_history 隐藏路径（L1226-1227）
    overlay._pending_records = list(records)  # [oldest, middle, newest]
    overlay._dirty = True

    # 模拟 show_overlay 触发 set_records(_pending_records)（L563-564）
    assert overlay._dirty is True
    overlay.set_records(overlay._pending_records)

    # 验证显示顺序：最新在最上方
    assert overlay._records[0].title == "newest"  # 顶部
    assert overlay._records[1].title == "middle"
    assert overlay._records[2].title == "oldest"  # 底部


def test_suggested_fix_would_break_order(qtbot):
    """证明建议的修复（_pending_records = _records.copy()）会破坏顺序

    模拟应用建议修复后的场景：
    1. set_records 第一次调用：_records=[newest, middle, oldest], _pending=[newest, ...]
    2. 假设再次 set_records(_pending)：reverse 后变成 [oldest, middle, newest]
    3. 显示顺序错误：oldest 在顶部
    """
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)

    records = _make_records()  # [oldest, middle, newest]

    # 第一次 set_records（按建议修复：_pending = _records.copy()）
    overlay.set_records(records)
    # 模拟建议的修复：将 _pending_records 改为 _records 的副本
    overlay._pending_records = overlay._records.copy()  # [newest, middle, oldest]

    # 假设再次调用 set_records(_pending_records)（例如再次 show_overlay）
    overlay._dirty = True
    overlay.set_records(overlay._pending_records)

    # 应用建议修复后：_records 会变成 [oldest, middle, newest] —— oldest 在顶部（错误！）
    assert overlay._records[0].title == "oldest"  # 错误的显示顺序
    assert overlay._records[2].title == "newest"  # newest 反而在底部


def test_full_manager_flow_display_order(qtbot):
    """端到端验证：ToastManager 隐藏浮层 → refresh → show_overlay → 显示顺序正确"""
    m = ToastManager(theme="dark", no_expired_history=False)
    qtbot.addWidget(m.container)

    # 添加 3 条记录到过期历史
    from toast import ExpiredHistory, ExpiredRecord
    history = ExpiredHistory()
    history.add(ExpiredRecord("oldest", "m", 1000.0, 2000.0))
    history.add(ExpiredRecord("middle", "m", 2000.0, 3000.0))
    history.add(ExpiredRecord("newest", "m", 3000.0, 4000.0))

    # 模拟 refresh_expired_history（浮层不可见）
    assert not m.container.overlay.isVisible()
    m.container.refresh_expired_history(history.all())

    # 验证 dirty 标记和 _pending_records
    assert m.container.overlay._dirty is True
    assert m.container.overlay._pending_records[0].title == "oldest"

    # 触发 show_overlay → set_records(_pending_records)
    m.container.overlay.show_overlay()

    # 验证显示顺序：最新在最上方
    assert m.container.overlay._records[0].title == "newest"
    assert m.container.overlay._records[1].title == "middle"
    assert m.container.overlay._records[2].title == "oldest"

    m.container.close()
