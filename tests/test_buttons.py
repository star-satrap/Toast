"""Qt 组件测试：CloseButton / LedPinButton"""
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from toast import CloseButton, LedPinButton


def test_close_button_init(qtbot):
    """22x22，theme 属性"""
    btn = CloseButton(theme="dark")
    qtbot.addWidget(btn)
    assert btn.theme == "dark"
    assert btn.minimumSize().width() == 22
    assert btn.minimumSize().height() == 22
    assert btn._hovered is False
    assert btn._pressed is False


def test_close_button_hover_pressed_state(qtbot):
    """enterEvent/leaveEvent/mousePressEvent 切换状态"""
    btn = CloseButton(theme="dark")
    qtbot.addWidget(btn)
    btn.resize(22, 22)
    btn.show()
    qtbot.waitExposed(btn)

    # 模拟 hover
    enter_event = QtGui.QEnterEvent(
        QtCore.QPointF(11, 11), QtCore.QPointF(11, 11), QtCore.QPointF(11, 11))
    btn.enterEvent(enter_event)
    assert btn._hovered is True

    # 模拟 pressed
    press_event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(11, 11), QtCore.QPointF(11, 11), QtCore.QPointF(11, 11),
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier)
    btn.mousePressEvent(press_event)
    assert btn._pressed is True

    # 模拟 release
    release_event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        QtCore.QPointF(11, 11), QtCore.QPointF(11, 11), QtCore.QPointF(11, 11),
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier)
    btn.mouseReleaseEvent(release_event)
    assert btn._pressed is False

    # 模拟 leave
    leave_event = QtCore.QEvent(QtCore.QEvent.Type.Leave)
    btn.leaveEvent(leave_event)
    assert btn._hovered is False
    assert btn._pressed is False


def test_led_pin_button_init_default_pinned(qtbot):
    """默认 pinned=True"""
    btn = LedPinButton(theme="dark")
    qtbot.addWidget(btn)
    assert btn.pinned is True
    assert btn.theme == "dark"
    assert btn._hovered is False


def test_led_pin_button_set_pinned(qtbot):
    """set_pinned(False) 后 pinned=False"""
    btn = LedPinButton(theme="dark")
    qtbot.addWidget(btn)
    assert btn.pinned is True
    btn.set_pinned(False)
    assert btn.pinned is False
    btn.set_pinned(True)
    assert btn.pinned is True


def test_led_pin_button_hover_toggle(qtbot):
    """enterEvent/leaveEvent 切换 _hovered"""
    btn = LedPinButton(theme="light")
    qtbot.addWidget(btn)
    btn.resize(22, 22)
    btn.show()
    qtbot.waitExposed(btn)

    enter_event = QtGui.QEnterEvent(
        QtCore.QPointF(11, 11), QtCore.QPointF(11, 11), QtCore.QPointF(11, 11))
    btn.enterEvent(enter_event)
    assert btn._hovered is True

    leave_event = QtCore.QEvent(QtCore.QEvent.Type.Leave)
    btn.leaveEvent(leave_event)
    assert btn._hovered is False
