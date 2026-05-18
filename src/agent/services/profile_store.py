from __future__ import annotations

from langgraph.store.base import BaseStore

_store: BaseStore | None = None


def bind_profile_store(store: BaseStore) -> None:
    global _store
    _store = store


def clear_profile_store() -> None:
    global _store
    _store = None


def get_profile_store() -> BaseStore:
    if _store is None:
        raise RuntimeError("Profile store is not initialized")
    return _store
