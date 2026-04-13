from bpy.types import Context

from .selection_controller import sync_selection_state
from .session import snapshot_for_tree
from .sync_common import bone_collection_for_context, collect_topology_signature
from .topology_controller import reconcile_tree_from_armature


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
    topology_signature = collect_topology_signature(bones)

    if should_arrange or snapshot.topology_signature != topology_signature:
        reconcile_tree_from_armature(
            context,
            armature,
            node_tree,
            should_arrange=should_arrange,
            bones=bones,
            snapshot=snapshot,
            topology_signature=topology_signature,
        )
        return

    sync_selection_state(
        context,
        armature,
        node_tree,
        bones=bones,
        snapshot=snapshot,
        topology_signature=topology_signature,
    )
