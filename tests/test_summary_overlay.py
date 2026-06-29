"""Qt 组件测试：ExpiredSummaryRow / ExpiredOverlay"""
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from toast import ExpiredSummaryRow, ExpiredOverlay, ExpiredRecord


def test_summary_row_init_zero_count(qtbot):
    """_count==0，paintEvent 不崩溃"""
    row = ExpiredSummaryRow(theme="dark")
    qtbot.addWidget(row)
    row.resize(300, 24)
    row.show()
    qtbot.waitExposed(row)
    assert row._count == 0
    assert row.height() == 24


def test_summary_row_set_count(qtbot):
    """set_count(5) 后 _count==5"""
    row = ExpiredSummaryRow(theme="dark")
    qtbot.addWidget(row)
    row.set_count(5)
    assert row._count == 5
    row.set_count(0)
    assert row._count == 0


def test_summary_row_clicked_signal(qtbot):
    """鼠标点击触发 clicked 信号"""
    row = ExpiredSummaryRow(theme="dark")
    qtbot.addWidget(row)
    row.resize(100, 24)
    row.show()
    qtbot.waitExposed(row)
    with qtbot.waitSignal(row.clicked, timeout=2000):
        qtbot.mouseClick(row, QtCore.Qt.MouseButton.LeftButton)


def test_summary_row_hover_signals(qtbot):
    """enterEvent 触发 hover_enter，leaveEvent 触发 hover_leave"""
    row = ExpiredSummaryRow(theme="dark")
    qtbot.addWidget(row)
    row.resize(100, 24)
    row.show()
    qtbot.waitExposed(row)

    # 验证 enter 信号触发
    with qtbot.waitSignal(row.hover_enter, timeout=2000):
        enter_event = QtGui.QEnterEvent(
            QtCore.QPointF(50, 12), QtCore.QPointF(50, 12), QtCore.QPointF(50, 12))
        row.enterEvent(enter_event)

    # 验证 leave 信号触发（用断言列表捕获）
    leave_received = []
    row.hover_leave.connect(lambda: leave_received.append(True))
    leave_event = QtCore.QEvent(QtCore.QEvent.Type.Leave)
    row.leaveEvent(leave_event)
    qtbot.wait(50)
    assert leave_received == [True]


def test_overlay_init_empty_records(qtbot):
    """set_records([]) 不崩溃，content_layout 仅 stretch（或 1 个 empty label）"""
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)
    overlay.set_records([])
    # 空列表会插入 empty QLabel
    assert overlay.content_layout.count() >= 1


def test_overlay_set_records_populates_rows(qtbot):
    """set_records([r1, r2]) 后 content 有 2 行 + 1 stretch"""
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)
    r1 = ExpiredRecord("title1", "msg1", 1000.0, 2000.0)
    r2 = ExpiredRecord("title2", "msg2", 2000.0, 3000.0)
    overlay.set_records([r1, r2])
    # 2 行 + 1 stretch = 3
    assert overlay.content_layout.count() == 3


def test_overlay_click_locked_toggle(qtbot):
    """set_click_locked 切换状态"""
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)
    assert overlay.is_click_locked() is False
    overlay.set_click_locked(True)
    assert overlay.is_click_locked() is True
    overlay.set_click_locked(False)
    assert overlay.is_click_locked() is False


def test_overlay_hover_grace_starts_timer(qtbot):
    """start_hover_grace() 创建 QTimer，cancel_hover_grace() 停止"""
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)
    overlay.set_click_locked(False)
    overlay.start_hover_grace()
    assert overlay._hover_grace_timer is not None
    assert overlay._hover_grace_timer.isActive()
    overlay.cancel_hover_grace()
    assert overlay._hover_grace_timer is None
