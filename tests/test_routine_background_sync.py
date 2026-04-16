import asyncio

import pytest
from sqlalchemy import select

from agent.api import routine_events
from agent.db.database import Base, create_session_factory, create_sqlite_engine
from agent.db.models import RoutineSource


@pytest.mark.parametrize("source_id", ["bb", "tis"])
def test_sync_managed_source_creates_named_source_and_reuses_sync_logic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    source_id: str,
):
    async def run() -> None:
        engine = create_sqlite_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
        session_factory = create_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await routine_events.ensure_routine_calendar_schema(session)
            await session.commit()

        calls: list[str] = []

        async def fake_replace(source: RoutineSource, db) -> list[int]:
            calls.append(source.title)
            assert db is not None
            return [7, 8]

        target = (
            "_replace_routines_from_bb"
            if source_id == routine_events.BB_SOURCE_TITLE
            else "_replace_routines_from_tis"
        )
        monkeypatch.setattr(routine_events, target, fake_replace)

        async with session_factory() as session:
            result = await routine_events.sync_managed_source(source_id, session)
            await session.commit()

            source = (
                await session.execute(
                    select(RoutineSource).where(RoutineSource.title == source_id)
                )
            ).scalar_one_or_none()

        await engine.dispose()

        assert result == {"message": "Routine updated", "ids": [7, 8], "source": source_id}
        assert calls == [source_id]
        assert source is not None
        assert source.title == source_id

    asyncio.run(run())
