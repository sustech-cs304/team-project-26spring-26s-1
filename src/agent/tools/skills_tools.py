"""Tools for reading locally installed skills."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain.tools import tool


DB_PATH = Path("./agent.db")


def _read_skill_markdown(md_path_text: str) -> tuple[str, int, bool, str | None]:
    md_path = Path(md_path_text)
    if not md_path.exists():
        return "", 0, False, f"Skill markdown not found: {md_path}"

    try:
        content = md_path.read_text(encoding="utf-8")
        return content, len(content), True, None
    except OSError as e:
        return "", 0, False, str(e)


def _fetch_installed_skills() -> list[dict]:
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT cloud_skill_id, name, description, markdown_path, downloaded_at, updated_at
            FROM local_skills
            ORDER BY updated_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "cloud_skill_id": int(row["cloud_skill_id"]),
                "name": str(row["name"]),
                "description": str(row["description"] or ""),
                "markdown_path": str(row["markdown_path"]),
                "downloaded_at": str(row["downloaded_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
        )
    return out


def get_installed_skill_summaries() -> list[dict]:
    """Helper for system prompt injection: only expose summary fields."""
    skills = _fetch_installed_skills()
    return [
        {
            "cloud_skill_id": item["cloud_skill_id"],
            "name": item["name"],
            "description": item["description"],
        }
        for item in skills
    ]


@tool
def read_installed_skills(
    cloud_skill_id: int | None = None,
    name: str | None = None,
    include_content: bool = False,
) -> dict:
    """Read locally installed skills.

    - Without parameters: return all installed skill summaries.
    - With `cloud_skill_id` or `name`: return one matching skill.
    - Set `include_content=true` to also return markdown content for the matched skill.
    - When content is included, response also carries `content_length` and `content_complete`.
    """
    skills = _fetch_installed_skills()
    if not skills:
        return {"success": True, "count": 0, "skills": []}

    if cloud_skill_id is None and (name is None or not name.strip()):
        summaries = []
        for item in skills:
            row = {
                "cloud_skill_id": item["cloud_skill_id"],
                "name": item["name"],
                "description": item["description"],
            }
            if include_content:
                content, content_length, content_complete, content_error = _read_skill_markdown(
                    item["markdown_path"]
                )
                row["content"] = content
                row["content_length"] = content_length
                row["content_complete"] = content_complete
                if content_error is not None:
                    row["content_error"] = content_error
            summaries.append(row)
        return {"success": True, "count": len(summaries), "skills": summaries}

    name_norm = (name or "").strip().lower()
    matched = None
    for item in skills:
        if cloud_skill_id is not None and item["cloud_skill_id"] == cloud_skill_id:
            matched = item
            break
        if name_norm and item["name"].strip().lower() == name_norm:
            matched = item
            break

    if matched is None:
        return {
            "success": False,
            "message": "Installed skill not found.",
            "cloud_skill_id": cloud_skill_id,
            "name": name,
        }

    result = {
        "success": True,
        "skill": {
            "cloud_skill_id": matched["cloud_skill_id"],
            "name": matched["name"],
            "description": matched["description"],
        },
    }

    if include_content:
        content, content_length, content_complete, content_error = _read_skill_markdown(
            matched["markdown_path"]
        )
        result["content"] = content
        result["content_length"] = content_length
        result["content_complete"] = content_complete
        if content_error is not None:
            result["content_error"] = content_error

    return result
