from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from agent.api.conversation_service import create_conversation, delete_conversation, search_conversations
from agent.db.models import Conversation, Message


pytestmark = pytest.mark.unit


class FakeCheckpointer:
    def __init__(self):
        self.deleted_threads: list[str] = []

    async def adelete_thread(self, conversation_id: str):
        self.deleted_threads.append(conversation_id)


class FakeGraph:
    def __init__(self):
        self.checkpointer = FakeCheckpointer()


def test_create_conversation_persists_uuid_title_and_timestamp(sqlite_session_factory, run_async):
    conversation = run_async(create_conversation(sqlite_session_factory, title="Design Review"))

    async def _load():
        async with sqlite_session_factory() as session:
            return await session.get(Conversation, conversation.id)

    stored = run_async(_load())

    assert uuid.UUID(conversation.id)
    assert stored is not None
    assert stored.title == "Design Review"
    assert stored.pinned is False
    assert stored.time_last_used is not None


def test_search_conversations_matches_title_or_message_terms_and_orders_pinned_first(
    sqlite_session_factory,
    run_async,
):
    older = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    newer = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    pinned_id = str(uuid.uuid4())
    message_match_id = str(uuid.uuid4())
    ignored_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add_all(
                [
                    Conversation(id=pinned_id, title="Pinned API Notes", pinned=True, time_last_used=older),
                    Conversation(id=message_match_id, title="Ordinary Chat", pinned=False, time_last_used=newer),
                    Conversation(id=ignored_id, title="Unrelated", pinned=True, time_last_used=newer),
                    Message(
                        id=str(uuid.uuid4()),
                        conversation_id=message_match_id,
                        seq=1,
                        content="This message contains API notes",
                    ),
                    Message(
                        id=str(uuid.uuid4()),
                        conversation_id=ignored_id,
                        seq=1,
                        content="No matching phrase",
                    ),
                ]
            )
            await session.commit()

    run_async(_seed())

    results = run_async(search_conversations(sqlite_session_factory, "api notes", page=1, page_size=10))

    assert [conversation.id for conversation in results] == [pinned_id, message_match_id]


def test_search_conversations_applies_pagination_after_sorting(sqlite_session_factory, run_async):
    ids = [str(uuid.uuid4()) for _ in range(3)]

    async def _seed():
        async with sqlite_session_factory() as session:
            for index, conversation_id in enumerate(ids):
                session.add(
                    Conversation(
                        id=conversation_id,
                        title=f"Shared Keyword {index}",
                        time_last_used=dt.datetime(2026, 1, index + 1, tzinfo=dt.timezone.utc),
                    )
                )
            await session.commit()

    run_async(_seed())

    page_two = run_async(search_conversations(sqlite_session_factory, "keyword", page=2, page_size=1))

    assert [conversation.id for conversation in page_two] == [ids[1]]


def test_delete_conversation_removes_messages_and_deletes_graph_thread(sqlite_session_factory, run_async):
    graph = FakeGraph()
    conversation_id = str(uuid.uuid4())

    async def _seed():
        async with sqlite_session_factory() as session:
            session.add(Conversation(id=conversation_id, title="Delete Me"))
            session.add(Message(id=str(uuid.uuid4()), conversation_id=conversation_id, seq=1, content="bye"))
            await session.commit()

    async def _count_messages():
        async with sqlite_session_factory() as session:
            result = await session.execute(select(Message).where(Message.conversation_id == conversation_id))
            return len(result.scalars().all())

    run_async(_seed())

    assert run_async(delete_conversation(sqlite_session_factory, graph, conversation_id)) is True
    assert run_async(_count_messages()) == 0
    assert graph.checkpointer.deleted_threads == [conversation_id]
    assert run_async(delete_conversation(sqlite_session_factory, graph, conversation_id)) is False
    assert graph.checkpointer.deleted_threads == [conversation_id]
