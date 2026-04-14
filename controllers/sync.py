from bpy.types import Context

from ..core.session import snapshot_for_tree
from ..domain.snapshot_collectors import collect_topology_snapshot
from ..domain.sync_common import bone_collection_for_context
from ..models.diff import diff_topology_state
from .selection_controller import sync_selection_state
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
    reparented_bone_names = set(topology_diff.reparented)
    reparented_bone_names.update(topology_diff.added)

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
                reparented_bone_names=reparented_bone_names if should_arrange else None,
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
                reparented_bone_names=reparented_bone_names if should_arrange else None,
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
