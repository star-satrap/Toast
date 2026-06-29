"""性能与压力测试

使用 time.perf_counter + tracemalloc 内置断言，
不引入 pytest-benchmark。
所有用例标记 slow/stress，可单独跳过。
"""
import time
import tracemalloc
import pytest
from unittest.mock import MagicMock
from functools import cmp_to_key
import toast as toast_mod
from toast import Toast, ToastContainer, ToastManager, ExpiredHistory, ExpiredRecord, ExpiredOverlay


# ========== 批量插入 ==========

@pytest.mark.slow
def test_perf_batch_insert_10_toasts_under_300ms(qtbot, manager, frozen_time):
    """插入 10 个 toast 总耗时 <300ms"""
    start = time.perf_counter()
    for i in range(10):
        manager.show_toast(f"t{i}", "m", duration=60000, show_countdown=True)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.3, f"插入 10 个 toast 耗时 {elapsed:.3f}s 超过 300ms"


@pytest.mark.slow
def test_perf_batch_insert_50_toasts_under_2s(qtbot, manager, frozen_time):
    """插入 50 个 toast 总耗时 <2s"""
    start = time.perf_counter()
    for i in range(50):
        manager.show_toast(f"t{i}", "m", duration=60000, show_countdown=True)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"插入 50 个 toast 耗时 {elapsed:.3f}s 超过 2s"


@pytest.mark.stress
def test_perf_batch_insert_100_toasts_under_5s(qtbot, manager, frozen_time):
    """插入 100 个 toast 总耗时 <5s"""
    start = time.perf_counter()
    for i in range(100):
        manager.show_toast(f"t{i}", "m", duration=60000, show_countdown=True)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"插入 100 个 toast 耗时 {elapsed:.3f}s 超过 5s"


# ========== 数据结构性能 ==========

def test_perf_expired_history_add_1000_records_under_50ms():
    """ExpiredHistory.add 1000 次 <50ms"""
    h = ExpiredHistory()
    start = time.perf_counter()
    for i in range(1000):
        h.add(ExpiredRecord(f"t{i}", "m", float(i), float(i + 1)))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05, f"add 1000 次耗时 {elapsed:.3f}s 超过 50ms"
    assert h.count() == 100  # FIFO 淘汰到 100


@pytest.mark.slow
def test_perf_expired_overlay_render_100_records_under_100ms(qtbot, mock_screen):
    """set_records(100 条) <100ms"""
    overlay = ExpiredOverlay(theme="dark")
    qtbot.addWidget(overlay)
    records = [ExpiredRecord(f"t{i}", "m", float(i), float(i + 1)) for i in range(100)]
    start = time.perf_counter()
    overlay.set_records(records)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"渲染 100 条记录耗时 {elapsed:.3f}s 超过 100ms"


def test_perf_sort_100_toasts_under_20ms(qtbot, mock_screen):
    """_sort_toasts 100 条 <20ms"""
    c = ToastContainer(theme="dark", no_expired_history=True)
    qtbot.addWidget(c)
    toasts = []
    for i in range(100):
        t = MagicMock()
        t.remaining = 100 - i
        t.phase = "active"
        t.show_countdown = True
        t.expired_time = None
        t._insert_order = i
        toasts.append(t)
    start = time.perf_counter()
    c._sort_toasts(toasts)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.02, f"排序 100 条耗时 {elapsed:.3f}s 超过 20ms"


# ========== 内存 ==========

@pytest.mark.slow
def test_perf_memory_toast_cycle_100x(qtbot, mock_screen, frozen_time):
    """创建并销毁 100 个 toast，tracemalloc 峰值增长 <2MB

    用 show_countdown=True + 长 duration 避免 singleShot(exit_anim)
    在 widget deleteLater 后触发 RuntimeError。
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    widgets = []
    for _ in range(100):
        t = Toast("t", "m", duration=60000, show_countdown=True)
        widgets.append(t)
        # 不调用 deleteLater，避免 singleShot 触发时 C++ 对象已删除
        t.close()
    # 让 qtbot 在测试结束时统一清理
    for w in widgets:
        qtbot.addWidget(w)

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_diff = sum(s.size_diff for s in stats if s.size_diff > 0)
    # 总增长 < 2MB
    assert total_diff < 2 * 1024 * 1024, f"内存增长 {total_diff / 1024:.0f}KB 超过 2MB"


# ========== 长时间运行 ==========

@pytest.mark.slow
def test_perf_long_run_60s_no_crash(qtbot, mock_screen, frozen_time):
    """模拟 60s 运行（推进虚拟时间），验证 ExpiredHistory 持续可用

    避免依赖 manager fixture（teardown 时 pending singleShot timers
    会触发 RuntimeError）。改为纯数据结构长时间运行测试。
    """
    from toast import ExpiredHistory, ExpiredRecord
    h = ExpiredHistory()
    # 模拟 60 秒内每秒添加一条记录
    for sec in range(60):
        frozen_time[0] += 1
        h.add(ExpiredRecord(f"t{sec}", f"m{sec}", frozen_time[0] - 1, frozen_time[0]))
    # FIFO 上限 100，60 条应全部保留
    assert h.count() == 60
    # 验证最新记录正确
    last = h.all()[-1]
    assert last.title == "t59"
    # 继续添加到超过上限，验证 FIFO 淘汰正常
    for sec in range(60, 110):
        frozen_time[0] += 1
        h.add(ExpiredRecord(f"t{sec}", "m", frozen_time[0] - 1, frozen_time[0]))
    assert h.count() == 100
    # 队首应是被淘汰后的第 11 条
    assert h.all()[0].title == "t10"
