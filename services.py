import bpy
from bpy.types import Armature, Context, Node

from .blender_context import active_theme, fallback_context
from .binding import ensure_bound_tree
from .constants import BONE_PALETTE_TO_INDEX_MAP, TREE_IDNAME


def bone_node_tree_of(context: Context) -> bpy.types.NodeTree | None:
    armature = armature_of(context)
    if armature is None:
        return None
    return ensure_bound_tree(armature)


def armature_of(context: Context) -> Armature | None:
    if context.object is not None and context.object.type == "ARMATURE":
        return context.object.data

    if getattr(context, "active_object", None) is not None and context.active_object.type == "ARMATURE":
        return context.active_object.data

    if context.pose_object is not None and context.pose_object.type == "ARMATURE":
        return context.pose_object.data

    view_layer = getattr(context, "view_layer", None)
    if view_layer is not None:
        active_obj = view_layer.objects.active
        if active_obj is not None and active_obj.type == "ARMATURE":
            return active_obj.data

    for obj in context.selected_objects:
        if obj.type == "ARMATURE":
            return obj.data

    global_context = fallback_context()
    if global_context is not None:
        if global_context.object is not None and global_context.object.type == "ARMATURE":
            return global_context.object.data
        if getattr(global_context, "active_object", None) is not None and global_context.active_object.type == "ARMATURE":
            return global_context.active_object.data

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
