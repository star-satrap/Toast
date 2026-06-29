"""24 小时常驻内存泄漏检测脚本（独立运行，不依赖 pytest-qt）"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import time
import tracemalloc
from unittest.mock import MagicMock
from PySide6 import QtCore, QtWidgets, QtNetwork

# 保存真实 perf_counter
_real_perf = time.perf_counter

import toast as toast_mod

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
screen = MagicMock()
screen.availableGeometry.return_value = QtCore.QRect(0, 0, 1920, 1080)
app.primaryScreen = lambda: screen

# 冻结 toast 内部时间
_t = [1700000000.0]
toast_mod.time.time = lambda: _t[0]


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ========== 1. Socket 泄漏检测 ==========
def test_socket_leak():
    section("1. IPC Socket 泄漏检测")
    srv = toast_mod.LocalServer(name="leak_test_srv")

    # 发送 N 条消息
    N = 50
    start = _real_perf()
    for i in range(N):
        toast_mod.send_message({"title": f"t{i}"}, name="leak_test_srv")
        app.processEvents()
    elapsed = _real_perf() - start

    # 检查残留 socket
    sockets = srv.server.findChildren(QtNetwork.QLocalSocket)
    active = []
    valid = []
    for s in sockets:
        try:
            if s.state() != QtNetwork.QLocalSocket.LocalSocketState.UnconnectedState:
                active.append(s)
            valid.append(s)
        except RuntimeError:
            pass  # C++ 对象已删除
    total = len(valid)

    print(f"  IPC 次数: {N}")
    print(f"  总耗时: {elapsed*1000:.0f}ms ({elapsed/N*1000:.1f}ms/次)")
    print(f"  活跃 socket: {len(active)}")
    print(f"  残留 socket 对象: {total}")
    if total > 0:
        print(f"  ⚠ 疑似泄漏: {total} 个 socket 未被 deleteLater")
        print(f"     原因: LocalServer.read_data() 仅 disconnectFromServer，未 deleteLater")
    else:
        print(f"  ✓ socket 已清理")

    srv.server.close()
    return total


# ========== 2. Toast 生命周期泄漏 ==========
def test_toast_lifecycle():
    section("2. Toast 创建/关闭循环（1000 轮）")
    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()

    m = toast_mod.ToastManager(theme="dark", no_expired_history=True)

    N = 1000
    for i in range(N):
        m.show_toast("t", "m", duration=3000, show_countdown=True)
        toast = m.toasts[-1]
        toast.closed.emit(toast)
        if i % 100 == 0:
            app.processEvents()

    app.processEvents()

    snap2 = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = snap2.compare_to(snap1, "lineno")
    total_diff = sum(s.size_diff for s in stats if s.size_diff > 0)

    container_toasts = m.container.vbox.count() - 1  # 减 stretch

    print(f"  循环次数: {N}")
    print(f"  manager.toasts 残留: {len(m.toasts)}")
    print(f"  container widget 残留: {container_toasts}")
    print(f"  Python 内存增长: {total_diff/1024:.0f} KB ({total_diff/N:.0f} bytes/轮)")

    if len(m.toasts) > 0:
        print(f"  ⚠ manager.toasts 未清空！")
    if container_toasts > 0:
        print(f"  ⚠ container widget 未清空！")
    if total_diff > 1024*1024:
        print(f"  ⚠ 内存增长 > 1MB")
    else:
        print(f"  ✓ 内存增长在可接受范围")

    m.container.close()
    return total_diff


# ========== 3. 模拟 24 小时运行 ==========
def test_simulated_24h():
    section("3. 模拟 24 小时运行（每 10s 一条通知，共 8640 条）")
    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()

    m = toast_mod.ToastManager(theme="dark", no_expired_history=False)

    N = 8640  # 24h / 10s
    start = _real_perf()
    for i in range(N):
        m.show_toast(f"t{i}", f"msg{i}", duration=3000, show_countdown=True)
        toast = m.toasts[-1]
        # 模拟过期 + 关闭
        _t[0] += 4
        toast._enter_expired_phase()
        _t[0] += 6
        toast.closed.emit(toast)

        if i % 1000 == 0:
            app.processEvents()
            elapsed = _real_perf() - start
            print(f"  进度: {i}/{N} ({i/N*100:.0f}%) 耗时: {elapsed:.1f}s toasts: {len(m.toasts)}")

    app.processEvents()

    snap2 = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = snap2.compare_to(snap1, "lineno")
    total_diff = sum(s.size_diff for s in stats if s.size_diff > 0)

    elapsed = _real_perf() - start
    history_count = m.expired_history.count() if m.expired_history else 0

    print(f"\n  总通知数: {N}")
    print(f"  总耗时: {elapsed:.1f}s")
    print(f"  manager.toasts 残留: {len(m.toasts)}")
    print(f"  expired_history 记录: {history_count}")
    print(f"  Python 内存增长: {total_diff/1024:.0f} KB ({total_diff/1024/1024:.1f} MB)")

    if len(m.toasts) == 0 and history_count == 100:
        print(f"  ✓ toasts 已清空，history FIFO 正常")
    else:
        print(f"  ⚠ 异常: toasts={len(m.toasts)}, history={history_count}")

    if total_diff > 10*1024*1024:
        print(f"  ⚠ 24h 内存增长 > 10MB，存在泄漏风险")
    else:
        print(f"  ✓ 24h 内存增长 < 10MB，无泄漏风险")

    m.container.close()
    return total_diff


# ========== 4. Qt C++ 对象计数 ==========
def test_qobject_count():
    section("4. Qt C++ 对象计数（前后对比）")
    m = toast_mod.ToastManager(theme="dark", no_expired_history=True)

    # 基准：创建 manager 后的对象数
    before = len(m.container.findChildren(QtCore.QObject))

    # 100 轮 create+close
    for i in range(100):
        m.show_toast("t", "m", duration=3000, show_countdown=True)
        toast = m.toasts[-1]
        toast.closed.emit(toast)
        app.processEvents()

    after = len(m.container.findChildren(QtCore.QObject))
    timer_count = len(m.container.findChildren(QtCore.QTimer))

    print(f"  创建 manager 后 QObject 数: {before}")
    print(f"  100 轮 create+close 后 QObject 数: {after}")
    print(f"  QTimer 数: {timer_count}")
    print(f"  增量: {after - before}")

    if after - before > 5:
        print(f"  ⚠ QObject 增量 > 5，可能存在 C++ 对象泄漏")
    else:
        print(f"  ✓ C++ 对象无明显泄漏")

    m.container.close()


# ========== 主入口 ==========
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Toast 24 小时常驻内存泄漏检测")
    print("="*60)

    socket_leak = test_socket_leak()
    toast_mem = test_toast_lifecycle()
    test_qobject_count()
    h24_mem = test_simulated_24h()

    section("总结")
    print(f"  Socket 残留: {socket_leak} 个")
    print(f"  1000 轮 toast 内存增长: {toast_mem/1024:.0f} KB")
    print(f"  24h 模拟内存增长: {h24_mem/1024:.0f} KB ({h24_mem/1024/1024:.1f} MB)")
    print()
