from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class EditorSyncState:
    armature_key: int | None = None
    tree_key: int | None = None
    mode: str | None = None
    pinned: bool = False
    window: object | None = None
    area: object | None = None
    region: object | None = None
    space: object | None = None
    last_seen_at: float = 0.0


_editor_states: dict[int, EditorSyncState] = {}


def editor_key_for_space(space) -> int:
    return int(space.as_pointer())


def update_editor_state(
    space,
    *,
    window=None,
    area=None,
    region=None,
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
    if window is not None:
        state.window = window
    if area is not None:
        state.area = area
    if region is not None:
        state.region = region
    state.space = space
    state.last_seen_at = monotonic()
    return changed


def remember_editor_context(context) -> bool:
    space = getattr(context, "space_data", None)
    if space is None or getattr(space, "type", None) != "NODE_EDITOR":
        return False

    key = editor_key_for_space(space)
    state = _editor_states.get(key)
    if state is None:
        state = EditorSyncState()
        _editor_states[key] = state

    window = getattr(context, "window", None)
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    changed = (
        state.window != window
        or state.area != area
        or state.region != region
        or state.space != space
    )

    state.window = window
    state.area = area
    state.region = region
    state.space = space
    state.last_seen_at = monotonic()
    return changed


def _runtime_editor_state_is_valid(state: EditorSyncState) -> bool:
    runtime_values = (state.window, state.area, state.region, state.space)
    if any(value is None for value in runtime_values):
        return False

    try:
        state.window.as_pointer()
        state.area.as_pointer()
        state.region.as_pointer()
        state.space.as_pointer()
        if state.area.type != "NODE_EDITOR":
            return False
        if state.region.type != "WINDOW":
            return False
        if state.space.type != "NODE_EDITOR":
            return False
    except (ReferenceError, AttributeError):
        return False

    return True


def iter_editor_contexts():
    for key, state in list(_editor_states.items()):
        if not _runtime_editor_state_is_valid(state):
            _editor_states.pop(key, None)
            continue
        yield state.window, state.area, state.region, state.space


def prune_editor_states(active_keys: set[int] | None = None):
    stale_keys = []
    for key, state in _editor_states.items():
        if active_keys is not None and key not in active_keys:
            stale_keys.append(key)
            continue
        if not _runtime_editor_state_is_valid(state):
            stale_keys.append(key)

    for key in stale_keys:
        _editor_states.pop(key, None)


def clear_all_editor_states():
    _editor_states.clear()
