# MinerU 异步文件解析工具

基于 [MinerU API](https://mineru.net)，将 PDF、Word、PPT、图片等文档异步解析为 Markdown / JSON，不阻塞调用方的事件循环。

---

## 目录结构

```
.
├── mineru_async_tool.py   # 异步解析工具（核心模块）
├── main.py                # 调用示例：解析 input/ 下的文件
├── config.yaml            # 配置文件（路径 & API Key）
├── input/                 # 待解析文件放置目录
└── output/                # 解析结果输出目录
```

---

## 配置文件 `config.yaml`

```yaml
paths:
  input_dir: "input"    # 待解析文件所在目录（相对于项目根目录）
  output_dir: "output"  # 解析结果输出目录（相对于项目根目录）

api-keys:
  MinerU: <your_token>  # 在 https://mineru.net 申请的 API Token
```

---

## 安装依赖

使用项目虚拟环境：

```bash
.venv\Scripts\python.exe -m pip install aiohttp PyYAML
```

---

## 核心 API

### `parse_files_with_mineru`

```python
from mineru_async_tool import parse_files_with_mineru

result = await parse_files_with_mineru(
    file_names: list[str],
    config_path: str = "config.yaml",
    poll_interval: int = 5,
    max_wait_seconds: int = 1800,
)
```

**参数说明**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file_names` | `list[str]` | 是 | — | 待解析的文件名列表（仅文件名，不含路径）。文件必须位于 `config.yaml` 配置的 `input_dir` 目录下 |
| `config_path` | `str` | 否 | `"config.yaml"` | 配置文件路径，相对于 `mineru_async_tool.py` 所在目录 |
| `poll_interval` | `int` | 否 | `5` | 轮询解析状态的间隔秒数 |
| `max_wait_seconds` | `int` | 否 | `1800` | 单批次最长等待时间（秒），超时后抛出 `TimeoutError` |

**支持的文件格式**

`.pdf` `.doc` `.docx` `.ppt` `.pptx` `.png` `.jpg` `.jpeg` `.html`

**返回值**

```python
{
    "input_dir": "/absolute/path/to/input",
    "output_dir": "/absolute/path/to/output",
    "batches": [
        {
            "batch_id": "95b9f8ae-25e9-4e7a-a7ff-0c47b2cb254f",
            "done": [
                {
                    "file_name": "example.pdf",
                    "state": "done",
                    "output_dir": "/absolute/path/to/output/<batch_id>/example"
                }
            ],
            "failed": [
                {
                    "file_name": "bad.pdf",
                    "state": "failed",
                    "err_msg": "解析失败原因"
                }
            ]
        }
    ]
}
```

解析结果解压到 `output/<batch_id>/<文件名（无扩展名）>/` 下，其中：
- `full.md` — Markdown 格式的解析结果
- `*_content_list.json` — 内容列表
- `*_model.json` — 模型推理结果
- `layout.json` — 中间处理结果（布局）

---

## 调用示例

### 在异步代码中嵌入

```python
import asyncio
from mineru_async_tool import parse_files_with_mineru

async def my_workflow():
    # 工具全程异步，不会阻塞当前事件循环
    result = await parse_files_with_mineru(
        file_names=["paper1.pdf", "slides.pptx"],
    )
    for batch in result["batches"]:
        for item in batch["done"]:
            print(f"已完成: {item['file_name']} -> {item['output_dir']}")

asyncio.run(my_workflow())
```

### 直接运行 `main.py`

`main.py` 会自动读取 `config.yaml` 中的 `input_dir`，取前两个可解析文件进行解析：

```bash
.venv\Scripts\python.exe main.py
```

---

## 工作流程

```
1. 读取 config.yaml → 获取 input_dir / output_dir / API Token
2. 按文件类型分组（html 使用 MinerU-HTML 模型，其他使用 vlm 模型）
3. 调用 /file-urls/batch 申请批量上传链接
4. 并发上传所有文件到 OSS 预签名 URL
5. 轮询 /extract-results/batch/{batch_id} 直到全部完成
6. 下载 full_zip_url 并解压到 output/<batch_id>/<文件名>/
```