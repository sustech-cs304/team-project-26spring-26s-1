from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import aiohttp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload embedding JSON files to /api/rag/import-embeddings")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base url, e.g. http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--json-file",
        action="append",
        type=Path,
        default=[],
        help="Embedding json file path, can be used multiple times",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=None,
        help="Directory containing *.embeddings.json files",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.embeddings.json",
        help="Glob pattern used with --json-dir",
    )
    parser.add_argument(
        "--overwrite-sources",
        type=str,
        default=None,
        help="Optional comma-separated source_file list passed to API",
    )
    return parser.parse_args()


def collect_json_files(args: argparse.Namespace) -> list[Path]:
    files: list[Path] = []
    files.extend(args.json_file)

    if args.json_dir is not None:
        files.extend(sorted(args.json_dir.glob(args.pattern)))

    normalized: list[Path] = []
    seen: set[Path] = set()
    for p in files:
        p = p.resolve()
        if p in seen:
            continue
        seen.add(p)
        normalized.append(p)
    return normalized


async def upload_one(
    session: aiohttp.ClientSession,
    endpoint: str,
    json_file: Path,
    overwrite_sources: str | None,
) -> tuple[int, str]:
    form = aiohttp.FormData()
    form.add_field(
        "embeddings_file",
        json_file.read_bytes(),
        filename=json_file.name,
        content_type="application/json",
    )
    if overwrite_sources:
        form.add_field("overwrite_sources", overwrite_sources)

    async with session.post(endpoint, data=form, timeout=aiohttp.ClientTimeout(total=1800)) as resp:
        body = await resp.text()
        return resp.status, body


async def _main_async() -> int:
    args = parse_args()
    files = collect_json_files(args)

    if not files:
        print("No embedding json file found. Use --json-file or --json-dir.")
        return 2

    missing = [p for p in files if not p.exists()]
    if missing:
        for p in missing:
            print(f"[missing] {p}")
        return 2

    endpoint = f"{args.base_url.rstrip('/')}/api/rag/import-embeddings"
    print(f"endpoint={endpoint}")

    failed = 0
    async with aiohttp.ClientSession() as session:
        for p in files:
            status, body = await upload_one(session, endpoint, p, args.overwrite_sources)
            print("---")
            print(f"file={p}")
            print(f"status={status}")
            print(f"response={body}")
            if status >= 400:
                failed += 1

    return 1 if failed else 0


def main() -> None:
    raise SystemExit(asyncio.run(_main_async()))


if __name__ == "__main__":
    main()
