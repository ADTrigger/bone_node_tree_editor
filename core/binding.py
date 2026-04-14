from __future__ import annotations

from uuid import uuid4

import bpy
from bpy.types import Armature, NodeTree

from .constants import CURRENT_SCHEMA_VERSION, SCHEMA_VERSION_KEY, TREE_IDNAME
from .session import clear_tree_session, mark_tree_dirty


ARMATURE_TREE_NAME_KEY = "bnte_node_tree_name"
TREE_ARMATURE_NAME_KEY = "bnte_armature_name"
ARMATURE_ID_KEY = "bnte_armature_id"
TREE_ID_KEY = "bnte_tree_id"
ARMATURE_BOUND_TREE_ID_KEY = "bnte_bound_tree_id"
TREE_BOUND_ARMATURE_ID_KEY = "bnte_bound_armature_id"
TREE_NAME_PREFIX = "BNTE::"

_armature_owner_pointers_by_id: dict[str, int] = {}
_tree_owner_pointers_by_id: dict[str, int] = {}


def clear_binding_runtime_state() -> None:
    _armature_owner_pointers_by_id.clear()
    _tree_owner_pointers_by_id.clear()


def _new_binding_id() -> str:
    return uuid4().hex


def _pointer(id_owner) -> int:
    return int(id_owner.as_pointer())


def _binding_value(id_owner, key: str) -> str | None:
    value = id_owner.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _ensure_unique_owner_id(id_owner, *, key: str, registry: dict[str, int]) -> str:
    pointer = _pointer(id_owner)
    stable_id = _binding_value(id_owner, key)
    if stable_id is None:
        stable_id = _new_binding_id()
        id_owner[key] = stable_id

    # Duplicated datablocks inherit custom properties, so copied IDs must be
    # refreshed before they can alias an existing binding target.
    owner_pointer = registry.get(stable_id)
    if owner_pointer is not None and owner_pointer != pointer:
        stable_id = _new_binding_id()
        id_owner[key] = stable_id

    registry[stable_id] = pointer
    return stable_id


def ensure_armature_id(armature: Armature) -> str:
    return _ensure_unique_owner_id(
        armature,
        key=ARMATURE_ID_KEY,
        registry=_armature_owner_pointers_by_id,
    )


def ensure_tree_id(node_tree: NodeTree) -> str:
    return _ensure_unique_owner_id(
        node_tree,
        key=TREE_ID_KEY,
        registry=_tree_owner_pointers_by_id,
    )


def _find_tree_by_id(tree_id: str | None) -> NodeTree | None:
    if tree_id is None:
        return None

    for node_tree in bpy.data.node_groups:
        if node_tree.bl_idname != TREE_IDNAME:
            continue
        if ensure_tree_id(node_tree) == tree_id:
            return node_tree
    return None


def _find_armature_by_id(armature_id: str | None) -> Armature | None:
    if armature_id is None:
        return None

    for armature in bpy.data.armatures:
        if ensure_armature_id(armature) == armature_id:
            return armature
    return None


def tree_name_for_armature(armature: Armature) -> str:
    return f"{TREE_NAME_PREFIX}{armature.name}"


def _is_name_bound_to_armature(armature: Armature, node_tree: NodeTree) -> bool:
    stored_tree_name = _binding_value(armature, ARMATURE_TREE_NAME_KEY)
    stored_armature_name = _binding_value(node_tree, TREE_ARMATURE_NAME_KEY)
    expected_tree_name = tree_name_for_armature(armature)

    if stored_armature_name is not None and stored_armature_name != armature.name:
        return False

    if stored_tree_name is not None and stored_tree_name != node_tree.name:
        return False

    if stored_armature_name == armature.name:
        return True

    if stored_tree_name == node_tree.name:
        return True

    return node_tree.name == expected_tree_name


def _has_explicit_id_binding(armature: Armature, node_tree: NodeTree) -> bool:
    return (
        _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY) is not None
        or _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY) is not None
    )


def is_tree_bound_to_armature(armature: Armature | None, node_tree: NodeTree | None) -> bool:
    if armature is None or node_tree is None or node_tree.bl_idname != TREE_IDNAME:
        return False

    armature_id = ensure_armature_id(armature)
    tree_id = ensure_tree_id(node_tree)
    stored_tree_id = _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY)
    stored_armature_id = _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY)

    if _has_explicit_id_binding(armature, node_tree):
        return stored_tree_id == tree_id and stored_armature_id == armature_id

    return _is_name_bound_to_armature(armature, node_tree)


def bind_tree_to_armature(armature: Armature, node_tree: NodeTree) -> NodeTree:
    armature_id = ensure_armature_id(armature)
    tree_id = ensure_tree_id(node_tree)
    previous_tree_id = _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY)
    previous_tree_name = _binding_value(armature, ARMATURE_TREE_NAME_KEY)
    previous_armature_id = _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY)
    previous_armature_name = _binding_value(node_tree, TREE_ARMATURE_NAME_KEY)

    previous_tree = None
    if previous_tree_id and previous_tree_id != tree_id:
        previous_tree = _find_tree_by_id(previous_tree_id)
    if previous_tree is None and previous_tree_name and previous_tree_name != node_tree.name:
        previous_tree = bpy.data.node_groups.get(previous_tree_name)
    if previous_tree is not None and previous_tree != node_tree:
        clear_tree_session(previous_tree)

    if previous_armature_id and previous_armature_id != armature_id:
        clear_tree_session(node_tree)
    elif previous_armature_name and previous_armature_name != armature.name:
        clear_tree_session(node_tree)

    armature[ARMATURE_ID_KEY] = armature_id
    node_tree[TREE_ID_KEY] = tree_id
    armature[ARMATURE_BOUND_TREE_ID_KEY] = tree_id
    node_tree[TREE_BOUND_ARMATURE_ID_KEY] = armature_id
    armature[ARMATURE_TREE_NAME_KEY] = node_tree.name
    node_tree[TREE_ARMATURE_NAME_KEY] = armature.name
    armature[SCHEMA_VERSION_KEY] = CURRENT_SCHEMA_VERSION
    node_tree[SCHEMA_VERSION_KEY] = CURRENT_SCHEMA_VERSION
    mark_tree_dirty(node_tree, "binding", "topology", "selection")
    return node_tree


def get_bound_tree(armature: Armature | None) -> NodeTree | None:
    if armature is None:
        return None

    ensure_armature_id(armature)
    stored_tree_id = _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY)
    if stored_tree_id is not None:
        node_tree = _find_tree_by_id(stored_tree_id)
        if is_tree_bound_to_armature(armature, node_tree):
            return node_tree
        return None

    node_groups = bpy.data.node_groups
    stored_name = _binding_value(armature, ARMATURE_TREE_NAME_KEY)
    if stored_name:
        node_tree = node_groups.get(stored_name)
        if is_tree_bound_to_armature(armature, node_tree):
            return bind_tree_to_armature(armature, node_tree)

    expected_name = tree_name_for_armature(armature)
    node_tree = node_groups.get(expected_name)
    if is_tree_bound_to_armature(armature, node_tree):
        return bind_tree_to_armature(armature, node_tree)

    if node_tree is not None and node_tree.bl_idname == TREE_IDNAME:
        return bind_tree_to_armature(armature, node_tree)

    for candidate in node_groups:
        if candidate.bl_idname != TREE_IDNAME:
            continue
        if candidate.get(TREE_ARMATURE_NAME_KEY) != armature.name:
            continue
        if is_tree_bound_to_armature(armature, candidate):
            return bind_tree_to_armature(armature, candidate)

    return None


def get_bound_armature(node_tree: NodeTree | None) -> Armature | None:
    if node_tree is None or node_tree.bl_idname != TREE_IDNAME:
        return None

    ensure_tree_id(node_tree)
    stored_armature_id = _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY)
    if stored_armature_id is not None:
        armature = _find_armature_by_id(stored_armature_id)
        if is_tree_bound_to_armature(armature, node_tree):
            return armature
        return None

    stored_armature_name = _binding_value(node_tree, TREE_ARMATURE_NAME_KEY)
    if stored_armature_name:
        armature = bpy.data.armatures.get(stored_armature_name)
        if is_tree_bound_to_armature(armature, node_tree):
            bind_tree_to_armature(armature, node_tree)
            return armature

    for armature in bpy.data.armatures:
        if armature.get(ARMATURE_TREE_NAME_KEY) != node_tree.name:
            continue
        if is_tree_bound_to_armature(armature, node_tree):
            bind_tree_to_armature(armature, node_tree)
            return armature

    if node_tree.name.startswith(TREE_NAME_PREFIX):
        expected_armature_name = node_tree.name.removeprefix(TREE_NAME_PREFIX)
        armature = bpy.data.armatures.get(expected_armature_name)
        if armature is not None:
            bind_tree_to_armature(armature, node_tree)
            return armature

    return None


def ensure_bound_tree(armature: Armature) -> NodeTree:
    ensure_armature_id(armature)
    node_tree = get_bound_tree(armature)
    if node_tree is not None:
        return node_tree

    node_tree = bpy.data.node_groups.new(tree_name_for_armature(armature), TREE_IDNAME)
    return bind_tree_to_armature(armature, node_tree)
