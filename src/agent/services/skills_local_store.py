from __future__ import annotations

import asyncio
import datetime as dt
import re
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.db.models import LocalSkill


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_skill_name(name: str, fallback: str) -> str:
    normalized = _SAFE_NAME_RE.sub("_", name.strip())
    normalized = normalized.strip("._-")
    return normalized or fallback


class SkillsLocalStore:
    """Local persistence for downloaded skills markdown files."""

    def __init__(self, session_factory: async_sessionmaker, root_path: str):
        self._session_factory = session_factory
        self._root_path = Path(root_path)
        self._lock = asyncio.Lock()

    async def list_downloaded_skills(self) -> list[LocalSkill]:
        async with self._session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(LocalSkill).order_by(LocalSkill.updated_at.desc())
            )
            return list(result.scalars().all())

    async def get_downloaded_skill_by_id(self, cloud_skill_id: int) -> LocalSkill | None:
        async with self._session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(LocalSkill).where(LocalSkill.cloud_skill_id == cloud_skill_id).limit(1)
            )
            return result.scalars().first()

    async def save_downloaded_skill(
        self,
        *,
        cloud_skill_id: int,
        name: str,
        description: str,
        markdown_content: str,
    ) -> LocalSkill:
        async with self._lock:
            safe_name = _safe_skill_name(name, fallback=f"skill_{cloud_skill_id}")
            skill_dir = self._root_path / str(cloud_skill_id)
            markdown_path = skill_dir / f"{safe_name}.md"

            await asyncio.to_thread(skill_dir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(markdown_path.write_text, markdown_content, "utf-8")

            now = dt.datetime.now(dt.timezone.utc)
            async with self._session_factory() as session:
                session: AsyncSession
                result = await session.execute(
                    select(LocalSkill).where(LocalSkill.cloud_skill_id == cloud_skill_id).limit(1)
                )
                row = result.scalars().first()
                if row is None:
                    row = LocalSkill(
                        cloud_skill_id=cloud_skill_id,
                        name=name,
                        description=description,
                        markdown_path=str(markdown_path.resolve()),
                        downloaded_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    row.name = name
                    row.description = description
                    row.markdown_path = str(markdown_path.resolve())
                    row.updated_at = now

                await session.commit()
                return row

    async def uninstall_local_skill(self, cloud_skill_id: int) -> bool:
        async with self._lock:
            async with self._session_factory() as session:
                session: AsyncSession
                result = await session.execute(
                    select(LocalSkill).where(LocalSkill.cloud_skill_id == cloud_skill_id).limit(1)
                )
                row = result.scalars().first()
                if row is None:
                    return False

                markdown_path = Path(row.markdown_path)
                skill_dir = markdown_path.parent

                await session.delete(row)
                await session.commit()

            if self._root_path in skill_dir.parents or skill_dir == self._root_path:
                await asyncio.to_thread(shutil.rmtree, skill_dir, True)
            elif markdown_path.exists():
                await asyncio.to_thread(markdown_path.unlink)
            return True
