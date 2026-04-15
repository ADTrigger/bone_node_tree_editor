import bpy
from bpy.types import Armature, Context, Node

from ..core.blender_context import (
    active_object_of,
    object_of,
    pose_object_of,
    selected_objects_of,
    view_layer_active_object_of,
)
from ..core.binding import ensure_bound_tree
from ..core.constants import BONE_NODE_HEADER_COLOR, TREE_IDNAME


def bone_node_tree_of(context: Context) -> bpy.types.NodeTree | None:
    armature = armature_of(context)
    if armature is None:
        return None
    return ensure_bound_tree(armature)


def armature_of(context: Context) -> Armature | None:
    obj = object_of(context)
    if obj is not None and obj.type == "ARMATURE":
        return obj.data

    active_obj = active_object_of(context)
    if active_obj is not None and active_obj.type == "ARMATURE":
        return active_obj.data

    pose_obj = pose_object_of(context)
    if pose_obj is not None and pose_obj.type == "ARMATURE":
        return pose_obj.data

    active_view_layer_obj = view_layer_active_object_of(context)
    if active_view_layer_obj is not None and active_view_layer_obj.type == "ARMATURE":
        return active_view_layer_obj.data

    for obj in selected_objects_of(context):
        if obj.type == "ARMATURE":
            return obj.data

    return None


def sync_bone_color_to_node(bone_color: bpy.types.BoneColor, node: Node):
    del bone_color
    node.use_custom_color = True
    node.color = BONE_NODE_HEADER_COLOR


def set_bone_select(bone, state: bool):
    bone.select = state
    bone.select_head = state
    bone.select_tail = state


def is_in_bone_node_tree(context: Context) -> bool:
    if context.space_data and context.space_data.tree_type == TREE_IDNAME:
        return True
    return False


def bone_collection_for_context(context: Context, armature):
    if context.mode == "EDIT_ARMATURE":
        return armature.edit_bones
    return armature.bones


def bone_parent_state(bone):
    if bone is None or bone.parent is None:
        return None, False
    return bone.parent.name, bool(getattr(bone, "use_connect", False))
