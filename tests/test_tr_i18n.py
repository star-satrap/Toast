"""纯单元测试：tr() 多语言回退"""
import pytest
import toast as toast_mod


def test_tr_default_lang_en(monkeypatch):
    """LANG='en' 时返回英文"""
    monkeypatch.setattr(toast_mod, "LANG", "en")
    assert toast_mod.tr("default_title") == "Default Notification"
    assert toast_mod.tr("pin_tooltip_pin") == "Pin"


def test_tr_lang_zh(monkeypatch):
    """LANG='zh' 返回中文"""
    monkeypatch.setattr(toast_mod, "LANG", "zh")
    assert toast_mod.tr("default_title") == "默认通知"
    assert toast_mod.tr("pin_tooltip_unpin") == "取消置顶"


def test_tr_missing_key_fallback(monkeypatch):
    """不存在的 key 返回 key 本身"""
    monkeypatch.setattr(toast_mod, "LANG", "en")
    assert toast_mod.tr("nonexistent_key_xyz") == "nonexistent_key_xyz"


def test_tr_missing_lang_fallback(monkeypatch):
    """key 存在但 LANG 不存在时回退到 key"""
    monkeypatch.setattr(toast_mod, "LANG", "fr")  # 法语未支持
    # key 存在但只有 en/zh，fr 不存在 → .get("fr", key) 返回 key
    assert toast_mod.tr("default_title") == "default_title"
