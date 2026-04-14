from bpy.types import Context

from .diff import diff_topology_state
from .selection_controller import sync_selection_state
from .session import snapshot_for_tree
from .snapshots import collect_topology_snapshot
from .sync_common import bone_collection_for_context
from .topology_controller import (
    needs_tree_rebuild,
    rebuild_tree_from_armature,
    reconcile_tree_from_armature,
)


def sync_tree_from_armature(
    context: Context,
    armature,
    node_tree,
    *,
    should_arrange: bool = False,
    snapshot=None,
):
    bones = bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    topology_snapshot = collect_topology_snapshot(bones)
    topology_diff = diff_topology_state(snapshot, topology=topology_snapshot)

    if should_arrange or topology_diff.has_changes:
        if needs_tree_rebuild(node_tree, bones=bones):
            rebuild_tree_from_armature(
                context,
                armature,
                node_tree,
                should_arrange=should_arrange,
                bones=bones,
                snapshot=snapshot,
                topology_snapshot=topology_snapshot,
            )
        else:
            reconcile_tree_from_armature(
                context,
                armature,
                node_tree,
                should_arrange=should_arrange,
                bones=bones,
                snapshot=snapshot,
                topology_snapshot=topology_snapshot,
            )
        return

    sync_selection_state(
        context,
        armature,
        node_tree,
        bones=bones,
        snapshot=snapshot,
        topology_snapshot=topology_snapshot,
    )
