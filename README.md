# Toast Notification Program / Toast通知程序

A cross-platform toast notification application built with PySide6, supporting custom messages, themes, multi-language (English/Chinese) display, touch gestures, and expired history tracking.

一款基于PySide6开发的跨平台Toast通知应用，支持自定义消息、主题切换、多语言（中英）显示、触摸手势及过期历史记录追踪。



## Features / 功能特性



- Customizable toast notifications with title and message / 支持自定义标题和消息的Toast通知
- Two themes: light and dark / 两种主题：浅色和深色
- Optional countdown timer display / 可选倒计时显示功能
- Support for long-duration notifications / 支持长时显示通知
- Multi-language support (automatically detects system language) / 多语言支持（自动检测系统语言）
- Pin/unpin functionality to keep notifications on top / 置顶/取消置顶功能，保持通知在窗口最上层
- Scrollable container when multiple notifications are present / 多通知时支持滚动的容器
- Local server mode to handle multiple notification requests / 本地服务器模式，处理多个通知请求
- Touch gesture support: right-swipe to close (Windows tablet adapted) / 触摸手势支持：右滑关闭（Windows平板适配）
- Expired history tracking with collapsible overlay / 到期历史记录追踪，支持折叠式浮层
- Dynamic sorting for countdown toasts (5s debounce) / 倒计时Toast动态排序（5秒防抖）
- Two-phase lifecycle: ACTIVE → EXPIRED with 5s buffer / 两阶段生命周期：ACTIVE → EXPIRED，含5秒缓冲
- Staggered batch insertion with 60ms delay increments / 批量插入错峰60ms延迟
- Custom QPainter-drawn buttons (LED pin indicator, red close) / 自定义QPainter绘制按钮（LED置顶指示灯、红色关闭）



## Requirements / 运行要求



- Python 3.9+ / Python 3.9及以上版本
- PySide6==6.7.3 (optimized for Windows Server 2016) / PySide6==6.7.3（针对Windows Server 2016优化）



## Installation / 安装步骤



```Plain Text
pip install pyside6==6.7.3
```



## Usage / 使用方法



### Basic Command / 基础命令



```Plain Text
python toast.py "Notification Title" "Notification Message" [duration]
```



### Parameters / 参数说明



|Parameter / 参数|Description / 描述|
|---|---|
|`title`|Notification title (optional, defaults to system language default) / 通知标题（可选，默认使用系统语言默认值）|
|`message`|Notification content (optional, defaults to system language default) / 通知内容（可选，默认使用系统语言默认值）|
|`duration`|Display time in milliseconds (optional, default: 4000) / 显示时长（毫秒，可选，默认：4000）|
|`--keep-alive`|Keep program running after all notifications are closed / 所有通知关闭后保持程序运行|
|`--show-countdown`|Show remaining time countdown in the notification / 在通知中显示剩余时间倒计时|
|`--theme`|Select theme (`light` or `dark`, default: `dark`) / 选择主题（`light`浅色或`dark`深色，默认：`dark`深色）|
|`--no-expired-history`|Disable expired history tracking (no summary row, no overlay) / 禁用到期历史记录功能（不显示摘要行，不创建浮层）|


### Examples / 使用示例



1. Basic notification: / 基础通知：

```Plain Text
python toast.py "Hello" "This is a test notification" 5000
```



2. Notification with countdown and light theme: / 带倒计时和浅色主题的通知：

```Plain Text
python toast.py "Reminder" "Meeting starts in 5 minutes" 300000 --show-countdown --theme light
```



3. Keep program running for future notifications: / 保持程序运行以接收后续通知：

```Plain Text
python toast.py --keep-alive
```



4. Disable expired history: / 禁用到期历史记录：

```Plain Text
python toast.py "Task" "Completed" 5000 --no-expired-history
```



## Features Details / 功能详情



- **Auto Language Detection / 自动语言检测**:
    - Automatically switches between English and Chinese based on system UI language / 根据系统UI语言自动切换中英文显示

- **Themes / 主题**: 
    - **Dark theme (default)**: Dark background with white text / 深色主题（默认）：深色背景配白色文字
    - **Light theme**: Light background with black text / 浅色主题：浅色背景配黑色文字

- **Custom Buttons / 自定义按钮**:
    - **LED Pin Button**: Green LED indicator when pinned, gray when unpinned (QPainter-drawn) / LED置顶按钮：置顶时绿色LED亮起，取消时灰色熄灭（QPainter自绘）
    - **Close Button**: Red background with white ✕, darkens on hover (QPainter-drawn) / 关闭按钮：红色背景白色✕，hover时加深（QPainter自绘）

- **Pinning / 置顶功能**:
    - Click the LED pin button to toggle "stay on top" functionality / 点击LED置顶按钮切换通知"置顶"状态

- **Close All / 全部关闭**:
    - Click the red close button to close all notifications and exit / 点击红色关闭按钮关闭所有通知并退出程序

- **Touch Gesture / 触摸手势**:
    - Right-swipe on a toast to close it (follows finger, 50% width threshold or fling ≥600px/s) / 右滑Toast可关闭（跟手滑动，50%宽度阈值或快速滑动≥600px/s触发）
    - Direction lock: vertical swipe scrolls the container, horizontal swipe triggers close / 方向锁定：垂直滑动滚动容器，水平滑动触发关闭
    - Gesture affects only the touched toast, not adjacent notifications / 手势仅作用于触摸的单条Toast，不影响相邻通知

- **Expired History / 到期历史记录**:
    - Summary row below toolbar shows expired count / 工具栏下方摘要行显示过期数量
    - Hover or click summary row to expand overlay with full history / hover或点击摘要行展开浮层显示完整历史
    - Records show time range and task description, sorted newest-first / 记录显示时间范围和任务描述，按时间倒序排列
    - FIFO with max 100 records (in-memory, not persisted) / FIFO淘汰，最多100条（内存存储，不持久化）

- **Dynamic Sorting / 动态排序**:
    - Countdown toasts sorted by remaining time (ascending) / 倒计时Toast按剩余时间升序排列
    - Expired toasts float to top with orange border / 过期Toast置顶并显示橙色边框
    - 5-second debounce to avoid frequent reordering / 5秒防抖避免频繁重排

- **Animations / 动画**:
    - Entry: slide in from right + fade in (200ms, OutCubic) / 入场：从右侧滑入+淡入（200ms，OutCubic）
    - Exit: slide out to right + fade out (150ms, InCubic) / 出场：向右侧滑出+淡出（150ms，InCubic）
    - Staggered batch insertion with 60ms delay increments / 批量插入错峰60ms延迟

- **Local Server / 本地服务器**:
    - Automatically starts a local server to handle multiple notification requests without restarting / 自动启动本地服务器，无需重启即可处理多个通知请求



## Deployment / 部署方法



You can deploy the application using pyside6-deploy: / 可使用pyside6-deploy工具进行应用部署：



```Plain Text
pyside6-deploy toast.py
```



## License / 许可证



[MIT](LICENSE)
