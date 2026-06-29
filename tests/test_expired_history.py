"""纯单元测试：ExpiredRecord / ExpiredHistory（无需 Qt）"""
import pytest
from toast import ExpiredRecord, ExpiredHistory


# ========== ExpiredRecord ==========
def test_record_slots_assignment():
    """ExpiredRecord 4 字段正确赋值"""
    r = ExpiredRecord("title", "msg", 1000.0, 2000.0)
    assert r.title == "title"
    assert r.message == "msg"
    assert r.created_at == 1000.0
    assert r.expired_at == 2000.0


def test_record_slots_attribute_error():
    """__slots__ 限制：访问未定义属性抛 AttributeError"""
    r = ExpiredRecord("t", "m", 0.0, 0.0)
    with pytest.raises(AttributeError):
        r.foo = "bar"
    with pytest.raises(AttributeError):
        _ = r.foo


# ========== ExpiredHistory ==========
def test_history_add_single(history):
    """add 单条，count==1，all 返回 1 条"""
    r = ExpiredRecord("t", "m", 0.0, 1.0)
    history.add(r)
    assert history.count() == 1
    assert len(history.all()) == 1
    assert history.all()[0] is r


def test_history_add_multiple_under_limit(history):
    """add 99 条，count==99"""
    for i in range(99):
        history.add(ExpiredRecord(f"t{i}", f"m{i}", float(i), float(i + 1)))
    assert history.count() == 99


def test_history_add_exactly_max(history):
    """add 100 条，count==100（不触发淘汰）"""
    for i in range(100):
        history.add(ExpiredRecord(f"t{i}", "m", float(i), float(i + 1)))
    assert history.count() == 100
    # 第 1 条仍在
    assert history.all()[0].title == "t0"


def test_history_fifo_eviction(history):
    """add 101 条，count==100，第 1 条被淘汰，all()[0] 是第 2 条"""
    for i in range(101):
        history.add(ExpiredRecord(f"t{i}", "m", float(i), float(i + 1)))
    assert history.count() == 100
    # 第 1 条已被淘汰，第 2 条成为新的队首
    assert history.all()[0].title == "t1"
    # 队尾仍是最后一条
    assert history.all()[-1].title == "t100"


def test_history_clear(history):
    """add 后 clear，count==0，all()==[]"""
    history.add(ExpiredRecord("t", "m", 0.0, 1.0))
    history.add(ExpiredRecord("t2", "m2", 1.0, 2.0))
    assert history.count() == 2
    history.clear()
    assert history.count() == 0
    assert history.all() == []


def test_history_all_returns_copy(history):
    """all() 返回列表的副本：修改不影响内部状态"""
    r1 = ExpiredRecord("t1", "m", 0.0, 1.0)
    r2 = ExpiredRecord("t2", "m", 1.0, 2.0)
    history.add(r1)
    history.add(r2)
    snapshot = history.all()
    snapshot.clear()  # 修改副本
    assert history.count() == 2  # 内部状态未受影响
    assert len(history.all()) == 2
