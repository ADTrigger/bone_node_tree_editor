import bpy
from bpy.types import Armature, NodeTree

from .constants import TREE_IDNAME
from .session import clear_tree_session, mark_tree_dirty


ARMATURE_TREE_NAME_KEY = "bnte_node_tree_name"
TREE_ARMATURE_NAME_KEY = "bnte_armature_name"
TREE_NAME_PREFIX = "BNTE::"


def tree_name_for_armature(armature: Armature) -> str:
    return f"{TREE_NAME_PREFIX}{armature.name}"


def is_tree_bound_to_armature(armature: Armature | None, node_tree: NodeTree | None) -> bool:
    if armature is None or node_tree is None or node_tree.bl_idname != TREE_IDNAME:
        return False

    stored_tree_name = armature.get(ARMATURE_TREE_NAME_KEY)
    stored_armature_name = node_tree.get(TREE_ARMATURE_NAME_KEY)
    expected_tree_name = tree_name_for_armature(armature)

    # Duplicated armatures inherit custom properties, so stale copied bindings
    # must be rejected when the tree still points at a different armature.
    if stored_armature_name is not None and stored_armature_name != armature.name:
        return False

    if stored_tree_name is not None and stored_tree_name != node_tree.name:
        return False

    if stored_armature_name == armature.name:
        return True

    if stored_tree_name == node_tree.name:
        return True

    return node_tree.name == expected_tree_name


def bind_tree_to_armature(armature: Armature, node_tree: NodeTree) -> NodeTree:
    previous_tree_name = armature.get(ARMATURE_TREE_NAME_KEY)
    if previous_tree_name and previous_tree_name != node_tree.name:
        previous_tree = bpy.data.node_groups.get(previous_tree_name)
        if previous_tree is not None and previous_tree != node_tree:
            clear_tree_session(previous_tree)

    armature[ARMATURE_TREE_NAME_KEY] = node_tree.name
    node_tree[TREE_ARMATURE_NAME_KEY] = armature.name
    mark_tree_dirty(node_tree, "binding", "topology", "selection")
    return node_tree


def get_bound_tree(armature: Armature | None) -> NodeTree | None:
    if armature is None:
        return None

    node_groups = bpy.data.node_groups
    stored_name = armature.get(ARMATURE_TREE_NAME_KEY)
    if stored_name:
        node_tree = node_groups.get(stored_name)
        if is_tree_bound_to_armature(armature, node_tree):
            return node_tree

    expected_name = tree_name_for_armature(armature)
    node_tree = node_groups.get(expected_name)
    if is_tree_bound_to_armature(armature, node_tree):
        return node_tree

    if node_tree is not None and node_tree.bl_idname == TREE_IDNAME:
        return bind_tree_to_armature(armature, node_tree)

    for candidate in node_groups:
        if candidate.bl_idname != TREE_IDNAME:
            continue
        if candidate.get(TREE_ARMATURE_NAME_KEY) == armature.name:
            return bind_tree_to_armature(armature, candidate)

    return None


def get_bound_armature(node_tree: NodeTree | None) -> Armature | None:
    if node_tree is None or node_tree.bl_idname != TREE_IDNAME:
        return None

    stored_armature_name = node_tree.get(TREE_ARMATURE_NAME_KEY)
    if stored_armature_name:
        armature = bpy.data.armatures.get(stored_armature_name)
        if is_tree_bound_to_armature(armature, node_tree):
            return armature

    for armature in bpy.data.armatures:
        if armature.get(ARMATURE_TREE_NAME_KEY) != node_tree.name:
            continue
        if is_tree_bound_to_armature(armature, node_tree):
            return armature

    if node_tree.name.startswith(TREE_NAME_PREFIX):
        expected_armature_name = node_tree.name.removeprefix(TREE_NAME_PREFIX)
        armature = bpy.data.armatures.get(expected_armature_name)
        if armature is not None:
            bind_tree_to_armature(armature, node_tree)
            return armature

    return None


def ensure_bound_tree(armature: Armature) -> NodeTree:
    node_tree = get_bound_tree(armature)
    if node_tree is not None:
        return node_tree

    node_tree = bpy.data.node_groups.new(tree_name_for_armature(armature), TREE_IDNAME)
    return bind_tree_to_armature(armature, node_tree)
