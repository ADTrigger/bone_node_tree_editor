from bpy.types import Context

from ..core.blender_context import set_active_vertex_group_by_name
from ..core.session import snapshot_for_tree
from ..domain.snapshot_collectors import (
    collect_bone_selection_snapshot,
    collect_node_selection_snapshot,
    collect_topology_snapshot,
)
from ..domain.services import set_bone_select
from ..domain.sync_common import bone_collection_for_context
from ..models.diff import diff_selection_state
from ..models.snapshots import (
    BoneSelectionSnapshot,
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
    topology_snapshot=None,
):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if node_state is None:
        node_state = collect_node_selection_snapshot(node_tree)
    if bone_state is None:
        bone_state = collect_bone_selection_snapshot(bones)

    node_active = node_state.active
    node_active_select = node_state.active_select
    node_selected = set(node_state.selected)
    bone_selected = set(bone_state.selected)

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
        node_selection=node_state,
        bone_selection=BoneSelectionSnapshot(
            active=active_bone_name,
            selected=frozenset(valid_selected_bones),
        ),
        topology=topology_snapshot,
    )


def sync_bone_selection_to_node(
    bones,
    node_tree,
    *,
    node_state=None,
    bone_state=None,
    snapshot=None,
    topology_snapshot=None,
):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)

    nodes = node_tree.nodes
    if bone_state is None:
        bone_state = collect_bone_selection_snapshot(bones)
    if node_state is None:
        node_state = collect_node_selection_snapshot(node_tree)

    bone_active = bone_state.active
    bone_selected = set(bone_state.selected)
    node_active = node_state.active
    node_selected = set(node_state.selected)

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

    sync_snapshot(
        snapshot,
        node_selection=collect_node_selection_snapshot(node_tree),
        bone_selection=bone_state,
        topology=topology_snapshot,
    )


def sync_selection_state(
    context: Context,
    armature,
    node_tree,
    *,
    bones=None,
    snapshot=None,
    topology_snapshot=None,
):
    if bones is None:
        bones = bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_snapshot is None:
        topology_snapshot = collect_topology_snapshot(bones)

    node_state = collect_node_selection_snapshot(node_tree)
    bone_state = collect_bone_selection_snapshot(bones)
    selection_diff = diff_selection_state(
        snapshot,
        node_selection=node_state,
        bone_selection=bone_state,
        topology=topology_snapshot,
    )

    if not selection_diff.has_changes:
        if selection_diff.topology_changed:
            sync_snapshot(snapshot, topology=topology_snapshot)
        return

    if selection_diff.should_sync_bone_to_node:
        sync_bone_selection_to_node(
            bones,
            node_tree,
            node_state=node_state,
            bone_state=bone_state,
            snapshot=snapshot,
            topology_snapshot=topology_snapshot,
        )
        return

    sync_node_selection_to_bone(
        context,
        bones,
        node_tree,
        node_state=node_state,
        bone_state=bone_state,
        snapshot=snapshot,
        topology_snapshot=topology_snapshot,
    )
