# Toast Notification App (中英文双语版)

# Toast Notification Program /  Toast通知程序

A cross-platform toast notification application built with PySide6, supporting custom messages, themes, and multi-language (English/Chinese) display. 

一款基于PySide6开发的跨平台Toast通知应用，支持自定义消息、主题切换及多语言（中英）显示。



## Features / 功能特性



- Customizable toast notifications with title and message / 支持自定义标题和消息的Toast通知

- Two themes: light and dark / 两种主题：浅色和深色

- Optional countdown timer display / 可选倒计时显示功能

- Support for long-duration notifications / 支持长时显示通知

- Multi-language support (automatically detects system language) / 多语言支持（自动检测系统语言）

- Pin/unpin functionality to keep notifications on top / 置顶/取消置顶功能，保持通知在窗口最上层

- Scrollable container when multiple notifications are present / 多通知时支持滚动的容器

- Local server mode to handle multiple notification requests / 本地服务器模式，处理多个通知请求



## Requirements / 运行要求



- Python 3.8+ / Python 3.8及以上版本

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


### Examples / 使用示例



1. Basic notification: / 基础通知：



```Plain Text

python toast.py "Hello" "This is a test notification" 5000
```



1. Notification with countdown and light theme: / 带倒计时和浅色主题的通知：



```Plain Text

python toast.py "Reminder" "Meeting starts in 5 minutes" 300000 --show-countdown --theme light
```



1. Keep program running for future notifications: / 保持程序运行以接收后续通知：



```Plain Text

python toast.py --keep-alive
```



## Features Details / 功能详情



- **Auto Language Detection / 自动语言检测**:
    
    - Automatically switches between English and Chinese based on system UI language / 根据系统UI语言自动切换中英文显示

- **Themes / 主题**: 

    - **Dark theme (default)**: Dark background with white text / 深色主题（默认）：深色背景配白色文字

    - **Light theme**: Light background with black text / 浅色主题：浅色背景配黑色文字

- **Pinning / 置顶功能**:

    - Click the 📌 button to toggle "stay on top" functionality / 点击📌按钮切换通知"置顶"状态

- **Close All / 全部关闭**:

    - Click the ❌ button to close all notifications and exit / 点击❌按钮关闭所有通知并退出程序

- **Fade Animations / 淡入淡出动画**:

    - Smooth fade in/out effects for better user experience / 流畅的淡入淡出效果，提升用户体验

- **Local Server / 本地服务器**:

    - Automatically starts a local server to handle multiple notification requests without restarting / 自动启动本地服务器，无需重启即可处理多个通知请求



## Deployment / 部署方法


You can deploy the application using pyside6-deploy: / 可使用pyside6-deploy工具进行应用部署：



```Plain Text

pyside6-deploy toast.py
```



## License / 许可证



[MIT](LICENSE)
