from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from .snapshots import TreeSyncSnapshot


@dataclass
class TreeSession:
    snapshot: TreeSyncSnapshot = field(default_factory=TreeSyncSnapshot)
    mutation_depth: int = 0
    last_sync_origin: str | None = None
    dirty_flags: set[str] = field(default_factory=set)
    next_selection_sync_at: float = 0.0

    @property
    def is_mutating(self) -> bool:
        return self.mutation_depth > 0

    def mark_dirty(self, *flags: str):
        for flag in flags:
            if flag:
                self.dirty_flags.add(flag)

    def clear_dirty(self, *flags: str):
        if not flags:
            self.dirty_flags.clear()
            return

        for flag in flags:
            self.dirty_flags.discard(flag)

    def has_dirty(self, *flags: str) -> bool:
        if not flags:
            return bool(self.dirty_flags)
        return any(flag in self.dirty_flags for flag in flags)

    def should_run_selection_fallback(self, *, now: float | None = None) -> bool:
        if now is None:
            now = monotonic()
        return now >= self.next_selection_sync_at

    def schedule_selection_fallback(self, interval: float, *, now: float | None = None):
        if now is None:
            now = monotonic()
        self.next_selection_sync_at = now + interval


TREE_SESSION_RUNTIME_KEY = "bnte_runtime_session_key"

_tree_sessions: dict[str, TreeSession] = {}
_tree_pointers_by_session_key: dict[str, int] = {}


def _new_tree_session_key() -> str:
    return uuid4().hex


def _tree_pointer(node_tree) -> int:
    return int(node_tree.as_pointer())


def _stored_session_key_for_tree(node_tree) -> str | None:
    session_key = node_tree.get(TREE_SESSION_RUNTIME_KEY)
    if isinstance(session_key, str) and session_key:
        return session_key
    return None


def _ensure_session_key_for_tree(node_tree) -> str:
    pointer = _tree_pointer(node_tree)
    session_key = _stored_session_key_for_tree(node_tree)
    if session_key is None:
        session_key = _new_tree_session_key()
        node_tree[TREE_SESSION_RUNTIME_KEY] = session_key

    # Duplicated node trees inherit custom properties, so a copied runtime
    # session key must be replaced before it can alias another tree session.
    owner_pointer = _tree_pointers_by_session_key.get(session_key)
    if owner_pointer is not None and owner_pointer != pointer:
        session_key = _new_tree_session_key()
        node_tree[TREE_SESSION_RUNTIME_KEY] = session_key

    _tree_pointers_by_session_key[session_key] = pointer
    return session_key


def prune_tree_sessions():
    import bpy

    live_session_keys: set[str] = set()
    live_pointers_by_key: dict[str, int] = {}

    for node_tree in bpy.data.node_groups:
        session_key = _stored_session_key_for_tree(node_tree)
        if session_key is None:
            continue
        live_session_keys.add(session_key)
        live_pointers_by_key[session_key] = _tree_pointer(node_tree)

    stale_session_keys = [key for key in _tree_sessions if key not in live_session_keys]
    for session_key in stale_session_keys:
        _tree_sessions.pop(session_key, None)

    stale_pointer_keys = [
        key for key in _tree_pointers_by_session_key if key not in live_session_keys
    ]
    for session_key in stale_pointer_keys:
        _tree_pointers_by_session_key.pop(session_key, None)

    _tree_pointers_by_session_key.update(live_pointers_by_key)


def session_for_tree(node_tree) -> TreeSession:
    session_key = _ensure_session_key_for_tree(node_tree)
    session = _tree_sessions.get(session_key)
    if session is None:
        session = TreeSession()
        _tree_sessions[session_key] = session
    return session


def snapshot_for_tree(node_tree) -> TreeSyncSnapshot:
    return session_for_tree(node_tree).snapshot


def mark_tree_dirty(node_tree, *flags: str):
    if node_tree is None:
        return
    session_for_tree(node_tree).mark_dirty(*flags)


def is_tree_mutating(node_tree) -> bool:
    if node_tree is None:
        return False
    return session_for_tree(node_tree).is_mutating


@contextmanager
def tree_mutation(node_tree, *, origin: str | None = None):
    if node_tree is None:
        yield None
        return

    session = session_for_tree(node_tree)
    if origin is not None:
        session.last_sync_origin = origin

    session.mutation_depth += 1
    try:
        yield session
    finally:
        session.mutation_depth = max(0, session.mutation_depth - 1)


def clear_tree_session(node_tree):
    if node_tree is None:
        return
    session_key = _stored_session_key_for_tree(node_tree)
    if session_key is None:
        return
    _tree_sessions.pop(session_key, None)
    _tree_pointers_by_session_key.pop(session_key, None)


def clear_all_tree_sessions():
    _tree_sessions.clear()
    _tree_pointers_by_session_key.clear()
