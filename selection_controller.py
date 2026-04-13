from bpy.types import Context

from .blender_context import set_active_vertex_group_by_name
from .services import set_bone_select
from .session import snapshot_for_tree
from .sync_common import (
    bone_collection_for_context,
    collect_bone_state,
    collect_node_state,
    collect_topology_signature,
    sync_snapshot,
)


def _sync_active_weight_group(context: Context, active_bone_name: str | None):
    if context.mode != "PAINT_WEIGHT" or context.object is None:
        return

    set_active_vertex_group_by_name(context.object, active_bone_name)


def sync_node_selection_to_bone(
    context: Context,
    bones,
    node_tree,
    *,
    node_state=None,
    bone_state=None,
    snapshot=None,
    topology_signature=None,
):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if node_state is None:
        node_state = collect_node_state(node_tree)
    if bone_state is None:
        bone_state = collect_bone_state(bones)

    node_active, node_active_select, node_selected = node_state
    _, bone_selected = bone_state

    valid_selected_bones = {bone_name for bone_name in node_selected if bones.get(bone_name) is not None}

    for bone_name in bone_selected - valid_selected_bones:
        bone = bones.get(bone_name)
        if bone is not None:
            set_bone_select(bone, False)

    for bone_name in valid_selected_bones - bone_selected:
        bone = bones.get(bone_name)
        if bone is not None:
            set_bone_select(bone, True)

    active_bone = None
    if node_active_select and node_active:
        active_bone = bones.get(node_active)

    if bones.active != active_bone:
        bones.active = active_bone

    active_bone_name = active_bone.name if active_bone else None
    if active_bone is not None:
        set_bone_select(active_bone, True)

    _sync_active_weight_group(context, active_bone_name)
    sync_snapshot(
        snapshot,
        node_state=node_state,
        bone_state=(active_bone_name, valid_selected_bones),
        topology_signature=topology_signature,
    )


def sync_bone_selection_to_node(
    bones,
    node_tree,
    *,
    node_state=None,
    bone_state=None,
    snapshot=None,
    topology_signature=None,
):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)

    nodes = node_tree.nodes
    if bone_state is None:
        bone_state = collect_bone_state(bones)
    if node_state is None:
        node_state = collect_node_state(node_tree)

    bone_active, bone_selected = bone_state
    node_active, _, node_selected = node_state

    valid_selected_nodes = {node_name for node_name in bone_selected if nodes.get(node_name) is not None}

    for node_name in node_selected - valid_selected_nodes:
        node = nodes.get(node_name)
        if node is not None:
            node.select = False

    for node_name in valid_selected_nodes - node_selected:
        node = nodes.get(node_name)
        if node is not None:
            node.select = True

    active_node = nodes.get(bone_active) if bone_active else None
    if node_active != (active_node.name if active_node else None):
        nodes.active = active_node

    active_node_name = active_node.name if active_node else None
    active_node_select = bool(active_node and active_node.select)
    sync_snapshot(
        snapshot,
        node_state=(active_node_name, active_node_select, valid_selected_nodes),
        bone_state=bone_state,
        topology_signature=topology_signature,
    )


def sync_selection_state(
    context: Context,
    armature,
    node_tree,
    *,
    bones=None,
    snapshot=None,
    topology_signature=None,
):
    if bones is None:
        bones = bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_signature is None:
        topology_signature = collect_topology_signature(bones)

    node_state = collect_node_state(node_tree)
    bone_state = collect_bone_state(bones)
    node_active, node_active_select, node_selected = node_state
    bone_active, bone_selected = bone_state

    node_changed = (
        snapshot.active != node_active
        or snapshot.active_select != node_active_select
        or snapshot.selected != node_selected
    )
    bone_changed = (
        snapshot.bone_active != bone_active
        or snapshot.bone_selected != bone_selected
    )

    if not node_changed and not bone_changed:
        if snapshot.topology_signature != topology_signature:
            sync_snapshot(snapshot, topology_signature=topology_signature)
        return

    if bone_changed and not node_changed:
        sync_bone_selection_to_node(
            bones,
            node_tree,
            node_state=node_state,
            bone_state=bone_state,
            snapshot=snapshot,
            topology_signature=topology_signature,
        )
        return

    sync_node_selection_to_bone(
        context,
        bones,
        node_tree,
        node_state=node_state,
        bone_state=bone_state,
        snapshot=snapshot,
        topology_signature=topology_signature,
    )
