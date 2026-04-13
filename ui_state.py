from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EditorSyncState:
    armature_key: int | None = None
    tree_key: int | None = None
    mode: str | None = None
    pinned: bool = False


_editor_states: dict[int, EditorSyncState] = {}


def editor_key_for_space(space) -> int:
    return int(space.as_pointer())


def update_editor_state(
    space,
    *,
    armature=None,
    node_tree=None,
    mode: str | None = None,
    pinned: bool = False,
) -> bool:
    key = editor_key_for_space(space)
    state = _editor_states.get(key)
    if state is None:
        state = EditorSyncState()
        _editor_states[key] = state

    next_armature_key = int(armature.as_pointer()) if armature is not None else None
    next_tree_key = int(node_tree.as_pointer()) if node_tree is not None else None

    changed = (
        state.armature_key != next_armature_key
        or state.tree_key != next_tree_key
        or state.mode != mode
        or state.pinned != pinned
    )

    state.armature_key = next_armature_key
    state.tree_key = next_tree_key
    state.mode = mode
    state.pinned = pinned
    return changed


def prune_editor_states(active_keys: set[int]):
    stale_keys = [key for key in _editor_states if key not in active_keys]
    for key in stale_keys:
        _editor_states.pop(key, None)


def clear_all_editor_states():
    _editor_states.clear()
