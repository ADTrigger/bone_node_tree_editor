import bpy
from bpy.types import Context

from .operators import OT_SyncBoneNodeSelection, OT_UpdateBoneNodeTree
from .services import armature_of, is_in_bone_node_tree, set_bone_select
from .state import old_node_tree_snapshot


def _collect_node_state(context: Context):
    active = context.active_node.name if context.active_node else None
    active_select = context.active_node.select if context.active_node else None
    selected = {}
    for node in context.selected_nodes:
        selected[node.name] = node.select
    return active, active_select, selected


def _collect_bone_state(bones):
    active = bones.active.name if bones.active else None
    selected = {}
    for bone in bones:
        if bone.select:
            selected[bone.name] = True
    return active, selected


def _is_state_dict_equal(state_a: dict, state_b: dict) -> bool:
    if len(state_a) != len(state_b):
        return False
    for key, value in state_a.items():
        if key not in state_b or state_b[key] != value:
            return False
    return True


def _sync_snapshot_from_node(context: Context):
    active, active_select, selected = _collect_node_state(context)
    old_node_tree_snapshot.active = active
    old_node_tree_snapshot.active_select = active_select
    old_node_tree_snapshot.selected = selected


def _sync_snapshot_from_bone(bones):
    active, selected = _collect_bone_state(bones)
    old_node_tree_snapshot.bone_active = active
    old_node_tree_snapshot.bone_selected = selected


def _sync_node_to_bone(context: Context, bones):
    for bone in bones:
        set_bone_select(bone, False)

    for node in context.selected_nodes:
        bone = bones.get(node.name)
        if bone:
            set_bone_select(bone, node.select)

    if context.active_node:
        bone = bones.get(context.active_node.name)
        if bone and context.active_node.select:
            bones.active = bone
            set_bone_select(bone, True)
            if context.mode == "PAINT_WEIGHT":
                if context.object.vertex_groups.get(bone.name):
                    bpy.ops.object.vertex_group_set_active(group=bone.name)
                else:
                    context.object.vertex_groups.active_index = -1
        else:
            bones.active = None
    else:
        bones.active = None

    _sync_snapshot_from_node(context)
    _sync_snapshot_from_bone(bones)


def _sync_bone_to_node(context: Context, bones):
    node_tree = context.space_data.edit_tree if context.space_data else None
    if node_tree is None:
        return

    nodes = node_tree.nodes
    bone_active, bone_selected = _collect_bone_state(bones)

    for node in nodes:
        node.select = False

    for bone_name in bone_selected:
        node = nodes.get(bone_name)
        if node:
            node.select = True

    if bone_active:
        nodes.active = nodes.get(bone_active)
    else:
        nodes.active = None

    _sync_snapshot_from_bone(bones)
    _sync_snapshot_from_node(context)


def _space_node_editor_draw():
    context = bpy.context

    if not is_in_bone_node_tree(context):
        return

    armature = armature_of(context)
    if armature is None:
        return

    bones = armature.edit_bones if context.mode == "EDIT_ARMATURE" else armature.bones

    node_active, node_active_select, node_selected = _collect_node_state(context)
    bone_active, bone_selected = _collect_bone_state(bones)

    node_changed = (
        old_node_tree_snapshot.active != node_active
        or old_node_tree_snapshot.active_select != node_active_select
        or not _is_state_dict_equal(old_node_tree_snapshot.selected, node_selected)
    )
    bone_changed = (
        old_node_tree_snapshot.bone_active != bone_active
        or not _is_state_dict_equal(old_node_tree_snapshot.bone_selected, bone_selected)
    )

    if not node_changed and not bone_changed:
        return

    if bone_changed and not node_changed:
        _sync_bone_to_node(context, bones)
        return

    _sync_node_to_bone(context, bones)


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
