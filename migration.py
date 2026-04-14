from __future__ import annotations

import bpy
from bpy.types import Armature, NodeTree

from .binding import (
    ARMATURE_BOUND_TREE_ID_KEY,
    ARMATURE_ID_KEY,
    ARMATURE_TREE_NAME_KEY,
    TREE_NAME_PREFIX,
    TREE_ARMATURE_NAME_KEY,
    TREE_BOUND_ARMATURE_ID_KEY,
    TREE_ID_KEY,
    bind_tree_to_armature,
    clear_binding_runtime_state,
    ensure_armature_id,
    ensure_tree_id,
    get_bound_armature,
    get_bound_tree,
    tree_name_for_armature,
)
from .constants import CURRENT_SCHEMA_VERSION, SCHEMA_VERSION_KEY, TREE_IDNAME


def schema_version_of(id_owner) -> int:
    if id_owner is None:
        return 0

    value = id_owner.get(SCHEMA_VERSION_KEY)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and value.is_integer():
        return max(0, int(value))
    return 0


def set_schema_version(id_owner, version: int = CURRENT_SCHEMA_VERSION) -> bool:
    if id_owner is None:
        return False
    if schema_version_of(id_owner) >= version and id_owner.get(SCHEMA_VERSION_KEY) == version:
        return False
    if schema_version_of(id_owner) < version:
        id_owner[SCHEMA_VERSION_KEY] = version
        return True
    return False


def _is_migratable(id_owner) -> bool:
    return schema_version_of(id_owner) <= CURRENT_SCHEMA_VERSION


def _binding_value(id_owner, key: str) -> str | None:
    value = id_owner.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _editor_trees():
    for node_tree in bpy.data.node_groups:
        if node_tree.bl_idname == TREE_IDNAME:
            yield node_tree


def _find_tree_by_id(tree_id: str | None) -> NodeTree | None:
    if tree_id is None:
        return None

    for node_tree in _editor_trees():
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


def _tree_named(name: str | None) -> NodeTree | None:
    if not name:
        return None
    node_tree = bpy.data.node_groups.get(name)
    if node_tree is None or node_tree.bl_idname != TREE_IDNAME:
        return None
    return node_tree


def _can_bind_tree_to_armature(armature: Armature, node_tree: NodeTree) -> bool:
    armature_id = ensure_armature_id(armature)
    tree_id = ensure_tree_id(node_tree)
    stored_tree_id = _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY)
    stored_armature_id = _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY)

    if stored_tree_id is not None and stored_tree_id != tree_id:
        return False
    if stored_armature_id is not None and stored_armature_id != armature_id:
        return False

    stored_tree_name = _binding_value(armature, ARMATURE_TREE_NAME_KEY)
    if stored_tree_name and stored_tree_name != node_tree.name:
        other_tree = _tree_named(stored_tree_name)
        if other_tree is not None and other_tree != node_tree:
            return False

    stored_armature_name = _binding_value(node_tree, TREE_ARMATURE_NAME_KEY)
    if stored_armature_name and stored_armature_name != armature.name:
        other_armature = bpy.data.armatures.get(stored_armature_name)
        if other_armature is not None and other_armature != armature:
            return False

    return True


def _candidate_tree_for_armature(armature: Armature) -> NodeTree | None:
    armature_id = ensure_armature_id(armature)
    stored_tree_id = _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY)
    stored_tree_name = _binding_value(armature, ARMATURE_TREE_NAME_KEY)

    for candidate in (
        _find_tree_by_id(stored_tree_id),
        _tree_named(stored_tree_name),
        _tree_named(tree_name_for_armature(armature)),
    ):
        if candidate is not None and _can_bind_tree_to_armature(armature, candidate):
            return candidate

    for node_tree in _editor_trees():
        if _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY) == armature_id:
            if _can_bind_tree_to_armature(armature, node_tree):
                return node_tree
        if _binding_value(node_tree, TREE_ARMATURE_NAME_KEY) == armature.name:
            if _can_bind_tree_to_armature(armature, node_tree):
                return node_tree

    return None


def _candidate_armature_for_tree(node_tree: NodeTree) -> Armature | None:
    tree_id = ensure_tree_id(node_tree)
    stored_armature_id = _binding_value(node_tree, TREE_BOUND_ARMATURE_ID_KEY)
    stored_armature_name = _binding_value(node_tree, TREE_ARMATURE_NAME_KEY)

    for candidate in (
        _find_armature_by_id(stored_armature_id),
        bpy.data.armatures.get(stored_armature_name) if stored_armature_name else None,
    ):
        if candidate is not None and _can_bind_tree_to_armature(candidate, node_tree):
            return candidate

    for armature in bpy.data.armatures:
        if _binding_value(armature, ARMATURE_BOUND_TREE_ID_KEY) == tree_id:
            if _can_bind_tree_to_armature(armature, node_tree):
                return armature
        if _binding_value(armature, ARMATURE_TREE_NAME_KEY) == node_tree.name:
            if _can_bind_tree_to_armature(armature, node_tree):
                return armature

    if node_tree.name.startswith(TREE_NAME_PREFIX):
        expected_armature = bpy.data.armatures.get(node_tree.name.removeprefix(TREE_NAME_PREFIX))
        if expected_armature is not None and _can_bind_tree_to_armature(expected_armature, node_tree):
            return expected_armature

    return None


def _owner_snapshot(id_owner, keys: tuple[str, ...]) -> tuple[object | None, ...]:
    return tuple(id_owner.get(key) for key in keys)


def migrate_armature_data(armature: Armature) -> bool:
    if not _is_migratable(armature):
        return False

    before = _owner_snapshot(
        armature,
        (
            ARMATURE_ID_KEY,
            ARMATURE_BOUND_TREE_ID_KEY,
            ARMATURE_TREE_NAME_KEY,
            SCHEMA_VERSION_KEY,
        ),
    )

    ensure_armature_id(armature)
    node_tree = get_bound_tree(armature)
    if node_tree is not None and not _is_migratable(node_tree):
        node_tree = None
    if node_tree is None:
        candidate = _candidate_tree_for_armature(armature)
        if candidate is not None and _is_migratable(candidate):
            node_tree = candidate
            bind_tree_to_armature(armature, node_tree)

    changed = set_schema_version(armature)
    if node_tree is not None:
        changed = set_schema_version(node_tree) or changed

    after = _owner_snapshot(
        armature,
        (
            ARMATURE_ID_KEY,
            ARMATURE_BOUND_TREE_ID_KEY,
            ARMATURE_TREE_NAME_KEY,
            SCHEMA_VERSION_KEY,
        ),
    )
    return changed or before != after


def migrate_node_tree_data(node_tree: NodeTree) -> bool:
    if node_tree.bl_idname != TREE_IDNAME:
        return False
    if not _is_migratable(node_tree):
        return False

    before = _owner_snapshot(
        node_tree,
        (
            TREE_ID_KEY,
            TREE_BOUND_ARMATURE_ID_KEY,
            TREE_ARMATURE_NAME_KEY,
            SCHEMA_VERSION_KEY,
        ),
    )

    ensure_tree_id(node_tree)
    armature = get_bound_armature(node_tree)
    if armature is not None and not _is_migratable(armature):
        armature = None
    if armature is None:
        candidate = _candidate_armature_for_tree(node_tree)
        if candidate is not None and _is_migratable(candidate):
            armature = candidate
            bind_tree_to_armature(armature, node_tree)

    changed = set_schema_version(node_tree)
    if armature is not None:
        changed = set_schema_version(armature) or changed

    after = _owner_snapshot(
        node_tree,
        (
            TREE_ID_KEY,
            TREE_BOUND_ARMATURE_ID_KEY,
            TREE_ARMATURE_NAME_KEY,
            SCHEMA_VERSION_KEY,
        ),
    )
    return changed or before != after


def migrate_all_data() -> dict[str, int]:
    clear_binding_runtime_state()

    result = {
        "armatures": 0,
        "node_trees": 0,
        "migrated_armatures": 0,
        "migrated_node_trees": 0,
    }

    for armature in bpy.data.armatures:
        result["armatures"] += 1
        if migrate_armature_data(armature):
            result["migrated_armatures"] += 1

    for node_tree in _editor_trees():
        result["node_trees"] += 1
        if migrate_node_tree_data(node_tree):
            result["migrated_node_trees"] += 1

    return result
