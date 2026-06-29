"""快速定位内存泄漏：逐步缩小范围"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import time
import tracemalloc
from unittest.mock import MagicMock
from PySide6 import QtCore, QtWidgets

_real_perf = time.perf_counter

import toast as toast_mod

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
screen = MagicMock()
screen.availableGeometry.return_value = QtCore.QRect(0, 0, 1920, 1080)
app.primaryScreen = lambda: screen

_t = [1700000000.0]
toast_mod.time.time = lambda: _t[0]


def measure_toast_cycle(N, use_expired=False, with_history=False):
    """测量 N 轮 toast create+close 的内存增长"""
    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()

    m = toast_mod.ToastManager(theme="dark", no_expired_history=not with_history)

    for i in range(N):
        m.show_toast(f"t{i}", "m", duration=3000, show_countdown=True)
        toast = m.toasts[-1]
        if use_expired:
            _t[0] += 4
            toast._enter_expired_phase()
            _t[0] += 6
        toast.closed.emit(toast)
        if i % 100 == 0:
            app.processEvents()

    app.processEvents()

    snap2 = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = snap2.compare_to(snap1, "lineno")
    total = sum(s.size_diff for s in stats if s.size_diff > 0)

    # 找出最大的几个分配点
    top = sorted(stats, key=lambda s: s.size_diff, reverse=True)[:5]

    m.container.close()
    return total, top, len(m.toasts)


print("="*60)
print("  内存泄漏快速定位")
print("="*60)

# 测试 1: 100 轮，无 expired phase
print("\n--- 100 轮 create+close（无 expired）---")
mem, top, leftover = measure_toast_cycle(100, use_expired=False)
print(f"  内存增长: {mem/1024:.0f} KB ({mem/100:.0f} bytes/轮)")
print(f"  toasts 残留: {leftover}")
for s in top:
    print(f"    {s.size_diff/1024:.1f}KB  {s.traceback}")

# 测试 2: 100 轮，有 expired phase
print("\n--- 100 轮 create+close（有 expired）---")
mem, top, leftover = measure_toast_cycle(100, use_expired=True)
print(f"  内存增长: {mem/1024:.0f} KB ({mem/100:.0f} bytes/轮)")
print(f"  toasts 残留: {leftover}")
for s in top:
    print(f"    {s.size_diff/1024:.1f}KB  {s.traceback}")

# 测试 3: 500 轮，有 expired phase + history
print("\n--- 500 轮 create+close（有 expired + history）---")
mem, top, leftover = measure_toast_cycle(500, use_expired=True, with_history=True)
print(f"  内存增长: {mem/1024:.0f} KB ({mem/500:.0f} bytes/轮)")
print(f"  toasts 残留: {leftover}")
hist_count = "N/A"
for s in top:
    print(f"    {s.size_diff/1024:.1f}KB  {s.traceback}")

# 测试 4: 1000 轮对比
print("\n--- 1000 轮 create+close（有 expired）---")
mem, top, leftover = measure_toast_cycle(1000, use_expired=True)
print(f"  内存增长: {mem/1024:.0f} KB ({mem/1024/1024:.1f} MB)")
print(f"  每轮增长: {mem/1000:.0f} bytes/轮")
print(f"  toasts 残留: {leftover}")
for s in top:
    print(f"    {s.size_diff/1024:.1f}KB  {s.traceback}")

# 测试 4b: 2000 轮，确认增长趋势
print("\n--- 2000 轮 create+close（有 expired + history）---")
mem, top, leftover = measure_toast_cycle(2000, use_expired=True, with_history=True)
print(f"  内存增长: {mem/1024:.0f} KB ({mem/1024/1024:.1f} MB)")
print(f"  每轮增长: {mem/2000:.0f} bytes/轮")
print(f"  toasts 残留: {leftover}")
for s in top:
    print(f"    {s.size_diff/1024:.1f}KB  {s.traceback}")

# 测试 5: 纯 create（不 close），看单个 toast 内存
print("\n--- 单个 toast 内存 ---")
tracemalloc.start()
snap1 = tracemalloc.take_snapshot()
m = toast_mod.ToastManager(theme="dark", no_expired_history=True)
m.show_toast("t", "m", duration=60000, show_countdown=True)
app.processEvents()
snap2 = tracemalloc.take_snapshot()
tracemalloc.stop()
stats = snap2.compare_to(snap1, "lineno")
total = sum(s.size_diff for s in stats if s.size_diff > 0)
print(f"  单个 toast: {total/1024:.1f} KB")
m.container.close()
