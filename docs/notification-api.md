# Notification API

## Overview

当前通知模块提供两个测试和集成用接口：

- `POST /api/notifications/dispatch`
- `GET /api/notifications/deeplink-preview/{resource}`

相关实现位于：

- [src/agent/api/notifications.py](../src/agent/api/notifications.py)
- [docs/notification-layer.md](./notification-layer.md)
- [docs/deeplink-spec.md](./deeplink-spec.md)

## POST /api/notifications/dispatch

发送一条桌面通知。通知可以包含：

- 标题和正文
- 点击整条通知时触发的 deeplink
- 一个或多个按钮，每个按钮也可以绑定独立 deeplink
- 通知分组键 `thread`
- 超时时间 `timeout_s`

### Request Body

```json
{
  "title": "任务执行完成",
  "message": "定时任务“同步课程表”已成功完成。",
  "level": "success",
  "deeplink": "opencrab://runs/0ccab874-8b91-49f8-b97c-b7309ab7a0df?tab=logs",
  "actions": [
    {
      "title": "打开任务",
      "deeplink": "opencrab://tasks/3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e"
    },
    {
      "title": "查看日志",
      "deeplink": "opencrab://runs/0ccab874-8b91-49f8-b97c-b7309ab7a0df?tab=logs"
    }
  ],
  "thread": "task:3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e",
  "timeout_s": 10
}
```

### Field Notes

- `title`: 通知标题，必填
- `message`: 通知正文，必填
- `level`: `info | success | warning | error`，可选，默认 `info`
- `deeplink`: 点击通知主体后的跳转地址，可选
- `actions`: 按钮列表，可选
- `thread`: 平台支持时用于分组，可选
- `timeout_s`: 超时时间秒数，可选

### Response Body

```json
{
  "status": "scheduled",
  "notification_id": null
}
```

### curl Example

```bash
curl -X POST "http://127.0.0.1:8000/api/notifications/dispatch" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "课程提醒",
    "message": "10 分钟后开始软件工程课",
    "level": "info",
    "deeplink": "opencrab://calendar/128?action=view&date=2026-04-12",
    "actions": [
      {
        "title": "打开日历",
        "deeplink": "opencrab://calendar/128?action=view&date=2026-04-12"
      }
    ],
    "thread": "calendar",
    "timeout_s": 8
  }'
```

## GET /api/notifications/deeplink-preview/{resource}

根据通知层规范生成一个标准化 deeplink，方便前后端对齐。

### Query Parameters

- `resource`: 路径参数，一级资源名，例如 `tasks`、`runs`、`calendar`
- `entity_id`: 可选，资源 id
- `action`: 可选，默认动作
- `tab`: 可选，默认标签页

### Response Body

```json
{
  "deeplink": "opencrab://tasks/3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e?action=history"
}
```

### curl Examples

```bash
curl "http://127.0.0.1:8000/api/notifications/deeplink-preview/tasks?entity_id=3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e&action=history"
```

```bash
curl "http://127.0.0.1:8000/api/notifications/deeplink-preview/calendar?entity_id=128&action=view&tab=agenda"
```

## Test Script

仓库内提供了一个测试脚本：

- [scripts/test_notifications.py](../scripts/test_notifications.py)
- [tests/test_notifications_api.py](../tests/test_notifications_api.py)

它会依次：

1. 调用 deeplink 预览接口
2. 用返回值组装通知请求
3. 调用通知派发接口
4. 打印完整请求和响应

同时也提供了更完整的 `pytest` 用例，适合回归测试和扩展样例。

### Run Examples

```bash
python scripts/test_notifications.py
```

```bash
python scripts/test_notifications.py --base-url http://127.0.0.1:8000 --resource tasks --entity-id demo-task --action history --tab logs
```

```bash
python scripts/test_notifications.py --title "自定义通知" --message "这是一个完整测试" --level warning --thread demo
```

### pytest Examples

```bash
pytest tests/test_notifications_api.py
```

```bash
pytest tests/test_notifications_api.py -k dispatch
```

```bash
pytest tests/test_notifications_api.py -k preview
```

### Covered Cases

- 最小通知请求
- 带按钮、deeplink、thread、timeout 的完整通知请求
- 缺少 `NotificationService` 时的 `503`
- 非法 `level` 的校验失败
- 常见资源的 deeplink 预览样例：
  `conversations`、`tasks`、`runs`、`calendar`、`settings`

## Test Notes

- 只有在桌面环境和通知后端可用时，系统弹窗才会实际出现。
- 即使接口返回成功，如果系统层不支持按钮或协议尚未注册，通知点击行为也可能不会生效。
- 当前脚本只依赖 Python 标准库，默认按 UTF-8 发送和解析 JSON。
- `pytest` 用例使用假的 `NotificationService`，不会真的弹出系统通知，更适合 CI 或回归测试。
