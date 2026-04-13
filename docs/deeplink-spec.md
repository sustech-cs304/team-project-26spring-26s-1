# Deeplink Spec

## Scheme

统一使用自定义协议：

```text
opencrab://<resource>/<entity_id>?action=<action>&tab=<tab>&...
```

- `scheme`: 固定为 `opencrab`
- `resource`: 一级资源名，建议与前端主路由语义保持一致
- `entity_id`: 可选，打开某个实体详情页
- `action`: 可选，表示默认交互，例如 `view`、`edit`、`history`
- `tab`: 可选，表示详情页默认激活的标签页
- 其余查询参数保留给具体业务模块扩展

## Resource 约定

- `opencrab://home`
- `opencrab://conversations/<conversation_id>`
- `opencrab://tasks/<task_id>`
- `opencrab://runs/<run_id>`
- `opencrab://calendar`
- `opencrab://calendar/<event_id>`
- `opencrab://settings/<section>`

## 典型示例

```text
opencrab://conversations/9f1f3c96-3977-4a4b-9d26-a1d90c7fd984
opencrab://tasks/3b11e1a9-7c45-40cf-9dd6-bbfa6308b54e?action=history
opencrab://runs/0ccab874-8b91-49f8-b97c-b7309ab7a0df?tab=logs
opencrab://calendar/128?action=view&date=2026-04-12
opencrab://settings/notifications
```

## 前端处理建议

- 前端桌面壳注册 `opencrab://` 自定义协议。
- 收到 deeplink 后先解析 `resource`，再根据 `entity_id`、`action` 和查询参数做导航。
- 未识别的 deeplink 不要崩溃，回退到首页并提示“暂不支持的链接”。
- 路由升级时保持向后兼容；如需破坏性修改，新增 `v` 查询参数而不是直接改老路径。
