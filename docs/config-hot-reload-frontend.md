# Config 热更新前端对接说明

## 概述

当前项目的 `config` 热更新能力已经在后端内部实现，核心逻辑位于：

- [src/agent/config.py](../src/agent/config.py)
- [tests/test_config_hot_reload.py](../tests/test_config_hot_reload.py)

它的本质是：

1. 启动时从 `config.yaml` 读取配置
2. 在进程内维护一份运行时配置对象
3. 允许通过 `patch_config(delta)` 对运行时配置做局部覆盖
4. 覆盖后，后续通过 `get_config()` 读取配置的模块会立刻拿到新值

## 当前真实状态

前端在接入前需要先明确一件事：

- 现在还没有对外开放的 `GET /api/config` / `PATCH /api/config` HTTP 接口
- 也没有 WebSocket / SSE 的“配置变更推送”
- 也没有数据库落库

当前配置的来源和生命周期是：

- 磁盘配置源：`config.yaml`
- 运行时配置源：进程内全局变量 `_config`
- 局部热更新：`patch_config(...)`
- 从磁盘重新覆盖运行时：`reload_config(...)`
- 将当前运行时配置写回磁盘：`save_config(...)`

所以从“前端对接”角度说，当前版本只能先对齐数据结构和更新语义，不能直接通过现有 HTTP API 完成配置读写。

## 热更新语义

### 1. 更新方式是“局部 patch + 全量校验”

后端的 `patch_config(delta)` 不是简单替换整个配置，而是：

1. 先把当前运行时配置转成字典
2. 将前端传入的 `delta` 做深度合并
3. 用合并后的完整结果重新走一遍 Pydantic 校验
4. 生成一个新的 `AppConfig` 对象替换旧对象

这意味着：

- 前端只需要传要修改的字段
- 未传字段会保留当前值
- 只要合并后的完整配置不合法，更新就应该整体失败

### 2. 热更新是“立刻生效”的

依赖 `get_config()` 的后端模块，在下一次读取配置时会自动拿到最新值。当前代码里已经验证过的例子包括：

- `OneBotHub`
- `ConfiguredModel`

这意味着前端如果未来接入配置修改接口，不需要额外做“通知后端重启”。

### 3. 热更新默认“不持久化到磁盘”

`patch_config(delta)` 只改内存，不会自动改 `config.yaml`。

如果希望修改在服务重启后依然保留，后端还需要额外调用：

```python
save_config()
```

所以前端要区分两个概念：

- 运行时热更新：立即生效，但重启可能丢失
- 持久化保存：写回 `config.yaml`，重启后仍保留

### 4. `reload_config()` 会用磁盘配置覆盖运行时配置

如果后端后续开放“从文件重新加载配置”的接口，那么它的行为应该理解为：

- 丢弃当前内存里的热更新结果
- 重新读取 `config.yaml`
- 用文件内容覆盖运行时配置

## 配置结构

当前 `AppConfig` 结构如下：

```ts
interface AppConfig {
  api: {
    agent: ApiEndpointConfig;
    utility: ApiEndpointConfig;
    embed: EmbedEndpointConfig;
    rerank: ApiEndpointConfig;
    asr: ASREndpointConfig;
  };
  file: {
    upload_path: string;
    mineru: {
      base_url: string;
      api_key: string;
    };
  };
  webfetch: {
    base_url: string;
    api_key: string;
    path: string;
    timeout_ms: number;
  };
  websearch: {
    base_url: string;
    api_key: string;
    path: string;
    timeout_ms: number;
  };
  onebot: {
    access_token: string;
    superuser_id: string;
    command_name: string;
  };
  notification: {
    enabled: boolean;
    app_name: string;
    app_icon: string | null;
    notification_limit: number | null;
    default_timeout_s: number;
    deeplink_scheme: string;
  };
}

interface ApiEndpointConfig {
  type: "OpenAI" | "Qwen" | "Anthropic";
  base_url: string;
  api_key: string;
  model: string;
}

interface EmbedEndpointConfig {
  type: "OpenAI";
  base_url: string;
  api_key: string;
  model: string;
  dims: number;
}

interface ASREndpointConfig {
  type: "Qwen";
  base_url: string;
  api_key: string;
}
```

## 前端展示建议

### 1. 表单按模块分组

建议前端按以下分组展示：

- `api.agent`
- `api.utility`
- `api.embed`
- `api.rerank`
- `api.asr`
- `file`
- `webfetch`
- `websearch`
- `onebot`
- `notification`

### 2. 敏感字段默认遮罩

以下字段建议默认密码框或遮罩展示：

- `api.*.api_key`
- `file.mineru.api_key`
- `webfetch.api_key`
- `websearch.api_key`
- `onebot.access_token`

如果后端后续开放读取接口，建议避免把这些值明文完整返回给前端，至少提供：

- `configured: boolean`
- `masked_value: string`

### 3. Patch 提交建议只传脏字段

推荐前端维护一份原始配置快照，提交时只发送改动过的字段。例如只改通知标题时：

```json
{
  "notification": {
    "app_name": "OpenCrab Desktop"
  }
}
```

只改 agent 模型时：

```json
{
  "api": {
    "agent": {
      "model": "gpt-5.2"
    }
  }
}
```

这和后端当前 `patch_config()` 的设计是匹配的。

## 推荐的前后端契约

虽然当前仓库里还没有配置 HTTP API，但如果要给前端正式对接，建议按下面这套契约开放。

### GET /api/config

用途：

- 获取当前运行时配置

建议响应：

```json
{
  "message": "OK",
  "data": {
    "api": {
      "agent": {
        "type": "OpenAI",
        "base_url": "https://example.com",
        "api_key": "******",
        "model": "gpt-4.1"
      }
    }
  }
}
```

说明：

- 建议敏感字段返回遮罩值，而不是明文
- 如果需要编辑密钥，可以额外设计单独的更新语义

### PATCH /api/config

用途：

- 对运行时配置做局部热更新

请求体示例：

```json
{
  "onebot": {
    "command_name": "#agent"
  },
  "notification": {
    "app_name": "OpenCrab"
  }
}
```

建议响应：

```json
{
  "message": "Config updated successfully."
}
```

语义要求：

- 按深度合并规则更新
- 用合并后的完整配置重新校验
- 校验失败时整体失败，不做部分写入

### POST /api/config/save

用途：

- 将当前运行时配置持久化到 `config.yaml`

建议响应：

```json
{
  "message": "Config saved successfully."
}
```

### POST /api/config/reload

用途：

- 丢弃当前运行时修改
- 从 `config.yaml` 重新加载配置

建议响应：

```json
{
  "message": "Config reloaded successfully."
}
```

## 前端交互建议

推荐的交互流程：

1. 页面初始化时获取当前配置
2. 用户编辑表单
3. 点击“应用”时调用热更新接口
4. 点击“保存到文件”时再调用持久化接口
5. 如果用户点击“从文件重新加载”，调用 reload 接口并刷新表单

建议区分两个按钮：

- `应用配置`
- `保存配置`

不要把两者混成一个动作，否则用户很难理解“为什么刷新后配置丢了”。

## 错误处理建议

前端需要重点处理两类错误：

### 1. 字段校验失败

例如：

- `type` 不在允许枚举内
- `timeout_ms` 不是数字
- 某个必填字段缺失

建议后端返回 `400`，前端展示“配置不合法”并尽量定位到字段。

### 2. 敏感字段误清空

如果前端采用“全量回传整个表单”，很容易把被遮罩的 `api_key` 错误覆盖成空字符串。

因此更推荐：

- 只传脏字段
- 对敏感字段单独编辑
- 未修改的密钥字段不要回传

## 当前前端对接结论

截至当前代码状态，可以给前端确认的结论是：

1. 后端已经支持运行时热更新，且是局部 patch、立即生效
2. 后端已经支持从文件重载、以及把当前配置写回文件
3. 这些能力目前还只是 Python 内部函数，不是 HTTP 接口
4. 前端若要真正接入，还需要后端补一层配置管理 API

如果后续补配置接口，前端应直接复用本文里的数据结构、patch 语义和“应用 / 保存”双阶段交互模型。
