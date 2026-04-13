from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from agent.config import config
from agent.main import app

EMBED_FILES = [
    Path("testdata_embeddings/2025级本科人才培养方案.embeddings.json"),
    Path("testdata_embeddings/南方科技大学学生手册20250718.embeddings.json"),
]


def cleanup_rag_data() -> None:
    rag_root = Path(config.file.rag_path)
    if rag_root.exists():
        shutil.rmtree(rag_root, ignore_errors=True)


def main() -> None:
    missing = [str(p) for p in EMBED_FILES if not p.exists()]
    if missing:
        print("missing_files=", missing)
        return

    try:
        with TestClient(app) as client:
            for emb_file in EMBED_FILES:
                with emb_file.open("rb") as f:
                    response = client.post(
                        "/api/rag/import-embeddings",
                        files={"embeddings_file": (emb_file.name, f, "application/json")},
                    )
                print("---")
                print("file=", emb_file.name)
                print("status=", response.status_code)
                try:
                    print("body=", response.json())
                except Exception:
                    print("body=", response.text)

        conn = sqlite3.connect("agent_store.db")
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT
              json_extract(value, '$.source_file') AS source_file,
              json_extract(value, '$.metadata.source_url') AS source_url,
              COUNT(*) AS cnt
            FROM store
            WHERE prefix='embeddings'
              AND json_extract(value, '$.source_file') IN ('2025级本科人才培养方案', '南方科技大学学生手册20250718')
            GROUP BY source_file, source_url
            ORDER BY source_file
            """
        ).fetchall()
        conn.close()

        print("---")
        print("db_check_rows=", rows)
    finally:
        cleanup_rag_data()
        print("---")
        print("cleanup= removed rag_data directory")


if __name__ == "__main__":
    main()
