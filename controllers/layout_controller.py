from ..core.blender_context import is_object_mode
from ..core.session import snapshot_for_tree, tree_mutation
from ..domain.snapshot_collectors import collect_node_layout_snapshot, node_layout_state
from ..models.snapshots import sync_snapshot


def should_restore_layout(context=None) -> bool:
    return is_object_mode(context)


def should_capture_layout(context=None) -> bool:
    return not should_restore_layout(context)


def capture_tree_layout_snapshot(node_tree, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    sync_snapshot(snapshot, node_layout=collect_node_layout_snapshot(node_tree))


def capture_node_layout_snapshot(node_tree, node, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    snapshot.node_layout[node.name] = node_layout_state(node)


def restore_locked_node_layout(node_tree, node, *, snapshot=None) -> bool:
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if not snapshot.node_layout:
        capture_tree_layout_snapshot(node_tree, snapshot=snapshot)
        return False

    layout_state = snapshot.node_layout.get(node.name)
    if layout_state is None:
        capture_node_layout_snapshot(node_tree, node, snapshot=snapshot)
        return False

    (x, y), width = layout_state
    if tuple(node.location) == (x, y) and node.width == width:
        return False

    with tree_mutation(node_tree, origin="restore_locked_node_layout"):
        if tuple(node.location) != (x, y):
            node.location = (x, y)
        if node.width != width:
            node.width = width
    return True


def restore_locked_tree_layout(node_tree, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if not snapshot.node_layout:
        capture_tree_layout_snapshot(node_tree, snapshot=snapshot)
        return

    with tree_mutation(node_tree, origin="restore_locked_tree_layout"):
        for node_name, ((x, y), width) in snapshot.node_layout.items():
            node = node_tree.nodes.get(node_name)
            if node is None:
                continue
            if tuple(node.location) != (x, y):
                node.location = (x, y)
            if node.width != width:
                node.width = width
