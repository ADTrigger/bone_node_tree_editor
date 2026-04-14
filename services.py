import bpy
from bpy.types import Armature, Context, Node

from .blender_context import (
    active_object_of,
    active_theme,
    object_of,
    pose_object_of,
    selected_objects_of,
    view_layer_active_object_of,
)
from .binding import ensure_bound_tree
from .constants import BONE_PALETTE_TO_INDEX_MAP, TREE_IDNAME


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
    if bone_color.is_custom:
        node.color = bone_color.custom.normal
        node.use_custom_color = True
    else:
        index = BONE_PALETTE_TO_INDEX_MAP.get(bone_color.palette)
        theme = active_theme()
        if theme is None:
            node.use_custom_color = False
            return
        if index is not None:
            color_set = theme.bone_color_sets[index]
            if color_set:
                node.color = color_set.normal
                node.use_custom_color = True
        else:
            node.use_custom_color = False


def set_bone_select(bone, state: bool):
    bone.select = state
    bone.select_head = state
    bone.select_tail = state


def is_in_bone_node_tree(context: Context) -> bool:
    if context.space_data and context.space_data.tree_type == TREE_IDNAME:
        return True
    return False
