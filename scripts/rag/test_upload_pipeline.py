from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

from agent.config import config
from scripts.rag.pipeline import run_rag_pipeline_for_file
from scripts.rag.paths import get_rag_paths

TEST_FILES = [
    Path("test_data/2025级本科人才培养方案.md"),
    Path("test_data/南方科技大学学生手册20250718.md"),
]


SOURCE_URL_BY_KEYWORD = {
    "培养方案": "https://tao.sustech.edu.cn/uploads/2025%E7%BA%A7%E6%9C%AC%E7%A7%91%E5%9F%B9%E5%85%BB%E6%96%B9%E6%A1%88-%E7%BB%88%E7%89%88-%E6%8C%82%E5%AE%98%E7%BD%91_1756369201.pdf",
    "学生手册": "https://osa.sustech.edu.cn/index.php?g=School&m=College&a=download&id=6488",
}

def resolve_source_url(raw_file: Path, explicit_source_url: str | None) -> str | None:
    if explicit_source_url:
        return explicit_source_url

    name = raw_file.stem
    for keyword, mapped_url in SOURCE_URL_BY_KEYWORD.items():
        if keyword in name:
            return mapped_url
    return None



async def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)

    for p in TEST_FILES:
        if not p.exists():
            print(f"missing: {p}")
            return

    for p in TEST_FILES:
        print("---")
        print("processing=", p)
        rag_paths = get_rag_paths(config)
        raw_copy = rag_paths.raw_dir / p.name
        raw_copy.write_bytes(p.read_bytes())
        result = await run_rag_pipeline_for_file(
            raw_file=raw_copy,
            config=config,
            store_db=Path("agent_store.db"),
            source_url=resolve_source_url(raw_copy, None),
        )
        print(
            "pipeline_result=",
            {
                "file": p.name,
                "chunks_count": result.chunks_count,
                "embedded_added": result.embedded_added,
                "embedded_overwritten": result.embedded_overwritten,
                "embedded_failed": result.embedded_failed,
            },
        )

    conn = sqlite3.connect("agent_store.db")
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
          json_extract(value, '$.source_file') AS source_file,
          json_extract(value, '$.metadata.source_url') AS source_url,
          COUNT(*) AS cnt
        FROM store
        WHERE prefix = 'embeddings'
          AND json_extract(value, '$.source_file') IN ('2025级本科人才培养方案', '南方科技大学学生手册20250718')
        GROUP BY source_file, source_url
        ORDER BY source_file
        """
    ).fetchall()
    conn.close()

    print("---")
    print("db_check_rows=", rows)


if __name__ == "__main__":
    asyncio.run(main())
