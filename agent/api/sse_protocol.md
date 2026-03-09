# Conversation Completion SSE Protocol

Endpoint: `POST /conversation/completion`
Content-Type: `text/event-stream`

Each SSE frame:

```text
event: <event_name>
data: <json>

```

## Event Order

1. Optional `history` (only when `need_history=true`)
2. Zero or more `thought_step` / `delta`
3. Final `done`
4. `error` may appear and terminate stream

## Events

### `history`

Sent once when `need_history=true`.

```json
{
  "conversation_id": "string",
  "created_at": 1772451893000,
  "updated_at": 1772451993000,
  "title": "string",
  "is_active": true,
  "is_pinned": false,
  "history_messages": [
    {
      "message_id": "string",
      "content": "string",
      "parent": "string",
      "role": "system|user|assistant|tool",
      "created_at": "1772451893000",
      "thought_steps": [
        {
          "id": "string",
          "type": "thought_steps|tool_call|tool_response",
          "content": "string",
          "status": "streaming|done|error",
          "create_at": "1772451893000",
          "raw_json": "{}"
        }
      ]
    }
  ]
}
```

### `delta`

```json
{
  "request_id": "string",
  "message_id": "assistant_message_id",
  "delta": "text chunk"
}
```

### `thought_step`

```json
{
  "request_id": "string",
  "message_id": "assistant_message_id",
  "step": {
    "id": "string",
    "type": "thought_steps|tool_call|tool_response",
    "content": "string",
    "status": "streaming|done|error",
    "create_at": "1772451893000",
    "raw_json": "{}"
  }
}
```

### `done`

```json
{
  "conversation_id": "string",
  "request_id": "string",
  "message_id": "assistant_message_id",
  "created_at": 1772451893000,
  "updated_at": 1772451993000,
  "title": "string",
  "is_active": true,
  "is_pinned": false
}
```

Empty-content (history-only) completion:

```json
{
  "request_id": "string",
  "reason": "empty_content"
}
```

### `error`

```json
{
  "request_id": "string",
  "message": "error detail"
}
```
