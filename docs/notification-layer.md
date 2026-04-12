# Notification Layer Design

## 目标

为后端提供一个“任意地方、任意线程、任意时间”都能调用的统一通知入口，并基于 `desktop-notifier` 发送桌面通知。

这一层负责：

- 统一通知模型，而不是在业务代码里直接拼 `desktop-notifier` 参数
- 将点击通知 / 点击按钮统一映射到 deeplink
- 在 FastAPI 主事件循环和后台线程之间做线程安全调度
- 屏蔽平台差异和依赖缺失时的降级行为

## 代码结构

- `src/agent/services/notification_service.py`
  - 通知领域模型：`AppNotification`、`NotificationAction`、`Deeplink`
  - 核心服务：`NotificationService`
- `src/agent/notifications.py`
  - 全局注册表，给非 Request 上下文代码使用
- `src/agent/api/notifications.py`
  - 手动验证与调试通知的 API

## 生命周期

- 在 `FastAPI` lifespan 启动时创建 `NotificationService`
- 将实例注入 `app.state.NotificationService`
- 同时写入 `agent.notifications` 的全局注册表
- 应用关闭时清理全局注册表

这样做之后：

- 路由层可以通过 `request.app.state.NotificationService`
- 后台线程或通用模块可以通过 `agent.notifications.notify(...)`

## 线程模型

`desktop-notifier` 的主 API是异步的，且点击/按钮回调依赖运行中的事件循环。当前实现里：

- FastAPI 主线程维护 asyncio event loop
- `NotificationService.send_async(...)` 供异步上下文直接 `await`
- `NotificationService.send(...)` 供任意线程调用
- 如果调用方不在主 loop 上，服务会用 `asyncio.run_coroutine_threadsafe(...)` 将发送任务切回主 loop

这使得像 `CronWatcher` 这类后台线程也可以安全发通知。

## 通知模型

`AppNotification` 的核心字段：

- `title`
- `message`
- `level`: `info | success | warning | error`
- `deeplink`: 点击整条通知后的跳转
- `actions`: 按钮列表，每个按钮也可以绑定一个 deeplink
- `thread`: 用于平台支持时做通知分组
- `timeout_s`

`level` 当前映射策略：

- `error` -> `Urgency.Critical`
- 其它级别 -> `Urgency.Normal`

后续如果你们想做更明显的视觉分级，可以继续细化。

## Deeplink 策略

通知层不直接关心前端页面实现，只约定统一的 URI 规范，并把 URI 作为点击结果打开。

详细规范见 [deeplink-spec.md](./deeplink-spec.md)。

服务内提供：

- `NotificationService.build_deeplink(...)`
- `Deeplink.route(...)`

这样业务代码不需要手写字符串拼接。

## 配置

`config.yaml` / `AppConfig` 中新增 `notification` 段：

```yaml
notification:
  enabled: true
  app_name: Agent
  app_icon: assets/opencrab.ico
  notification_limit: 8
  default_timeout_s: 10
  deeplink_scheme: opencrab
```

## 使用示例

异步上下文：

```python
from agent.services import AppNotification, NotificationAction, NotificationLevel

service = request.app.state.NotificationService

await service.send_async(
    AppNotification(
        title="任务执行完成",
        message="点击查看运行日志",
        level=NotificationLevel.success,
        deeplink=service.build_deeplink("runs", run_id, tab="logs"),
        actions=(
            NotificationAction(
                title="打开任务",
                deeplink=service.build_deeplink("tasks", task_id),
            ),
        ),
        thread=f"task:{task_id}",
    )
)
```

任意线程 / 通用模块：

```python
from agent.notifications import notify, get_notification_service
from agent.services import AppNotification, NotificationLevel

service = get_notification_service()
if service:
    notify(
        AppNotification(
            title="课程提醒",
            message="10 分钟后开始软件工程课",
            level=NotificationLevel.info,
            deeplink=service.build_deeplink("calendar", event_id, action="view"),
            thread="calendar",
        )
    )
```

## 降级行为

- 如果 `desktop-notifier` 未安装，服务会记录 warning，并静默跳过发送
- 如果当前平台不支持某些能力，例如按钮或附件，库本身会忽略不支持的字段
- 如果自定义协议尚未被前端桌面壳注册，点击通知时会打开失败，但不会影响通知本身的展示
