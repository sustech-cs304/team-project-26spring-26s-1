"""
mineru_async_tool.py
--------------------
异步 MinerU 文件解析工具。

对外暴露唯一入口：
    async def parse_files_with_mineru(
        file_names: list[str],
        config_path: str = "config.yaml",
        poll_interval: int = 5,
        max_wait_seconds: int = 1800,
    ) -> dict

参数：
    file_names        - 待解析的文件名列表（不含路径，仅文件名），文件必须位于
                        config.yaml 配置的 input_dir 目录下
    config_path       - 配置文件路径（相对于本模块所在目录），默认 config.yaml
    poll_interval     - 轮询结果的间隔秒数，默认 5
    max_wait_seconds  - 单批次最大等待秒数，默认 1800

返回：
    {
        "input_dir": "...",
        "output_dir": "...",
        "batches": [
            {
                "batch_id": "...",
                "done": [{"file_name": "...", "state": "done", "output_dir": "..."}],
                "failed": [{"file_name": "...", "state": "failed", "err_msg": "..."}]
            }
        ]
    }
"""

import asyncio
import io
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp
import yaml


API_BASE = "https://mineru.net/api/v4"
SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".html"}
NON_HTML_MODEL = "vlm"
HTML_MODEL = "MinerU-HTML"
TERMINAL_STATES = {"done", "failed"}


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def _build_auth_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _post_json(session: aiohttp.ClientSession, url: str, payload: dict) -> dict:
    async with session.post(url, json=payload) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


async def _get_json(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


async def _put_file(session: aiohttp.ClientSession, upload_url: str, file_path: Path) -> None:
    data = file_path.read_bytes()
    # 上传预签名 OSS URL 时：
    # 1. 不能携带 Authorization 头（该 URL 本身已签名）
    # 2. 不能设置 Content-Type（aiohttp 默认会注入 application/octet-stream，导致 OSS 403）
    async with aiohttp.ClientSession(skip_auto_headers=["Content-Type"]) as upload_session:
        async with upload_session.put(upload_url, data=data) as response:
            response.raise_for_status()


async def _download_bytes(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.read()


async def _extract_zip(zip_content: bytes, target_dir: Path) -> None:
    await asyncio.to_thread(_extract_zip_sync, zip_content, target_dir)


def _extract_zip_sync(zip_content: bytes, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
        zf.extractall(target_dir)


async def _request_upload_urls(
    session: aiohttp.ClientSession,
    files: List[Path],
    model_version: str,
) -> Tuple[str, List[str]]:
    url = f"{API_BASE}/file-urls/batch"
    payload = {
        "files": [{"name": fp.name, "data_id": fp.stem} for fp in files],
        "model_version": model_version,
    }
    body = await _post_json(session, url, payload)

    if body.get("code") != 0:
        raise RuntimeError(f"申请上传链接失败: {json.dumps(body, ensure_ascii=False)}")

    data = body.get("data", {})
    batch_id: str = data.get("batch_id", "")
    upload_urls: List[str] = data.get("file_urls", [])

    if not batch_id or not upload_urls:
        raise RuntimeError(f"响应缺少 batch_id 或 file_urls: {json.dumps(body, ensure_ascii=False)}")
    if len(upload_urls) != len(files):
        raise RuntimeError("返回上传 URL 数量与文件数量不一致")

    return batch_id, upload_urls


async def _poll_batch_result(
    session: aiohttp.ClientSession,
    batch_id: str,
    poll_interval: int,
    max_wait_seconds: int,
) -> List[dict]:
    url = f"{API_BASE}/extract-results/batch/{batch_id}"
    start = asyncio.get_running_loop().time()

    while True:
        body = await _get_json(session, url)
        if body.get("code") != 0:
            raise RuntimeError(f"查询批量结果失败: {json.dumps(body, ensure_ascii=False)}")

        extract_result: List[dict] = body.get("data", {}).get("extract_result", [])
        if extract_result:
            summary = ", ".join(
                f"{item.get('file_name', '?')}={item.get('state', '?')}"
                for item in extract_result
            )
            print(f"[POLL] batch_id={batch_id} | {summary}")

            if all(item.get("state") in TERMINAL_STATES for item in extract_result):
                return extract_result

        elapsed = asyncio.get_running_loop().time() - start
        if elapsed > max_wait_seconds:
            raise TimeoutError(f"轮询超时: batch_id={batch_id}, 已等待 {int(elapsed)} 秒")

        await asyncio.sleep(poll_interval)


async def _handle_result_item(
    session: aiohttp.ClientSession,
    item: dict,
    batch_dir: Path,
) -> dict:
    file_name = item.get("file_name", "unknown")
    state = item.get("state", "failed")

    if state != "done":
        err_msg = item.get("err_msg", "")
        print(f"[FAILED] {file_name} -> {err_msg}")
        return {"file_name": file_name, "state": state, "err_msg": err_msg}

    zip_url = item.get("full_zip_url", "")
    if not zip_url:
        print(f"[WARN] {file_name} done 但缺少 full_zip_url")
        return {"file_name": file_name, "state": "failed", "err_msg": "缺少 full_zip_url"}

    target_dir = batch_dir / Path(file_name).stem
    zip_content = await _download_bytes(session, zip_url)
    await _extract_zip(zip_content, target_dir)
    print(f"[DONE] {file_name} -> {target_dir}")
    return {"file_name": file_name, "state": "done", "output_dir": str(target_dir)}


async def _process_group(
    session: aiohttp.ClientSession,
    files: List[Path],
    model_version: str,
    output_dir: Path,
    poll_interval: int,
    max_wait_seconds: int,
) -> dict:
    print(f"\n[GROUP] model={model_version}, files={len(files)}")

    batch_id, upload_urls = await _request_upload_urls(session, files, model_version)
    print(f"[BATCH] batch_id={batch_id}")

    # 并发上传所有文件
    await asyncio.gather(*(_put_file(session, url, fp) for fp, url in zip(files, upload_urls)))
    for fp in files:
        print(f"[UPLOAD] {fp.name} -> success")

    results = await _poll_batch_result(session, batch_id, poll_interval, max_wait_seconds)

    batch_dir = output_dir / batch_id
    item_results = await asyncio.gather(
        *(_handle_result_item(session, item, batch_dir) for item in results)
    )

    done = [r for r in item_results if r["state"] == "done"]
    failed = [r for r in item_results if r["state"] != "done"]
    return {"batch_id": batch_id, "done": done, "failed": failed}


async def parse_files_with_mineru(
    file_names: List[str],
    config_path: str = "config.yaml",
    poll_interval: int = 5,
    max_wait_seconds: int = 1800,
) -> dict:
    """
    异步解析指定文件列表，不阻塞当前事件循环。

    Args:
        file_names:        待解析的文件名列表（仅文件名，路径从 config.yaml 读取）
        config_path:       配置文件路径（相对于本模块所在目录）
        poll_interval:     轮询间隔秒数
        max_wait_seconds:  单批次最长等待秒数

    Returns:
        解析结果字典，包含每个批次的 done/failed 信息及输出路径
    """
    root = Path(__file__).resolve().parent
    config = _load_config((root / config_path).resolve())

    input_dir = (root / config.get("paths", {}).get("input_dir", "input")).resolve()
    output_dir = (root / config.get("paths", {}).get("output_dir", "output")).resolve()
    token: str = config.get("api-keys", {}).get("MinerU", "").strip()

    if not token:
        raise ValueError("config.yaml 中缺少 api-keys.MinerU")
    if not input_dir.is_dir():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 解析并校验文件路径
    resolved_files: List[Path] = []
    for name in file_names:
        fp = (input_dir / name).resolve()
        if not fp.is_file():
            raise FileNotFoundError(f"文件不存在: {fp}")
        if fp.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {fp.name}")
        resolved_files.append(fp)

    # 按模型分组
    groups: Dict[str, List[Path]] = {}
    for fp in resolved_files:
        model = HTML_MODEL if fp.suffix.lower() == ".html" else NON_HTML_MODEL
        groups.setdefault(model, []).append(fp)

    print(f"共接收 {len(resolved_files)} 个文件，分 {len(groups)} 个模型批次解析。")

    headers = _build_auth_headers(token)
    batch_results = []

    async with aiohttp.ClientSession(headers=headers) as session:
        for model_version, group_files in groups.items():
            result = await _process_group(
                session=session,
                files=group_files,
                model_version=model_version,
                output_dir=output_dir,
                poll_interval=poll_interval,
                max_wait_seconds=max_wait_seconds,
            )
            batch_results.append(result)

    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "batches": batch_results,
    }
