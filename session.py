from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import monotonic


@dataclass
class TreeSyncSnapshot:
    active: str | None = None
    active_select: bool | None = None
    selected: set[str] = field(default_factory=set)
    bone_active: str | None = None
    bone_selected: set[str] = field(default_factory=set)
    topology_signature: frozenset = field(default_factory=frozenset)
    node_layout: dict[str, tuple[tuple[float, float], float]] = field(default_factory=dict)


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


_tree_sessions: dict[int, TreeSession] = {}


def _session_key_for_tree(node_tree) -> int:
    return int(node_tree.as_pointer())


def session_for_tree(node_tree) -> TreeSession:
    key = _session_key_for_tree(node_tree)
    session = _tree_sessions.get(key)
    if session is None:
        session = TreeSession()
        _tree_sessions[key] = session
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
    _tree_sessions.pop(_session_key_for_tree(node_tree), None)


def clear_all_tree_sessions():
    _tree_sessions.clear()
