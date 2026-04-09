import bpy
from bpy.types import Context

from .nodes import BoneNodeTree
from .operators import OT_SyncBoneNodeSelection, OT_UpdateBoneNodeTree
from .services import armature_of, is_in_bone_node_tree, set_bone_select
from .state import old_node_tree_snapshot


def _space_node_editor_draw():
    is_dirty = False
    context = bpy.context

    if not is_in_bone_node_tree(context):
        return

    if context.active_node and not context.active_node.hide:
        context.active_node.hide = True

    if context.active_node is None:
        if old_node_tree_snapshot.active is not None:
            is_dirty = True
    elif old_node_tree_snapshot.active is None:
        if context.active_node is not None:
            is_dirty = True
    elif old_node_tree_snapshot.active != context.active_node.name:
        is_dirty = True
    elif context.active_node == old_node_tree_snapshot.active:
        is_dirty = context.active_node.select != old_node_tree_snapshot.active_select

    if not is_dirty:
        match_num = 0
        for sel_node in context.selected_nodes:
            if sel_node.name in old_node_tree_snapshot.selected:
                match_num += 1
            else:
                is_dirty = True
                break
        if match_num != len(old_node_tree_snapshot.selected):
            is_dirty = True

    if is_dirty:
        armature = armature_of(context)
        if armature is not None:
            if context.mode == "EDIT_ARMATURE":
                bones = armature.edit_bones
            else:
                bones = armature.bones

            for bone in bones:
                set_bone_select(bone, False)

            old_node_tree_snapshot.selected.clear()
            for node in context.selected_nodes:
                old_node_tree_snapshot.selected[node.name] = node.select
                bone = bones.get(node.name)
                if bone:
                    set_bone_select(bone, node.select)

            if context.active_node:
                bone = bones.get(context.active_node.name)
                if bone and context.active_node.select:
                    bones.active = bone
                    set_bone_select(bone, True)
                    old_node_tree_snapshot.active_select = True
                    if context.mode == "PAINT_WEIGHT":
                        if context.object.vertex_groups.get(bone.name):
                            bpy.ops.object.vertex_group_set_active(group=bone.name)
                        else:
                            context.object.vertex_groups.active_index = -1
                else:
                    old_node_tree_snapshot.active_select = False
                old_node_tree_snapshot.active = context.active_node.name
            else:
                bones.active = None
                old_node_tree_snapshot.active = None


def _draw_pie(this: bpy.types.Menu, context: Context):
    if is_in_bone_node_tree(context):
        pie = this.layout.menu_pie()
        pie.operator(OT_SyncBoneNodeSelection.bl_idname, icon="UV_SYNC_SELECT")
        pie.operator(OT_UpdateBoneNodeTree.bl_idname, icon="OUTLINER_DATA_ARMATURE")


def register_ui_hooks():
    old_node_tree_snapshot.handler = bpy.types.SpaceNodeEditor.draw_handler_add(
        _space_node_editor_draw,
        (),
        old_node_tree_snapshot.region,
        "POST_PIXEL",
    )
    bpy.types.NODE_MT_view_pie.append(_draw_pie)


def unregister_ui_hooks():
    bpy.types.NODE_MT_view_pie.remove(_draw_pie)
    bpy.types.SpaceNodeEditor.draw_handler_remove(
        old_node_tree_snapshot.handler,
        old_node_tree_snapshot.region,
    )
