from .session import snapshot_for_tree, tree_mutation
from .sync_common import collect_node_layout, node_layout_state, sync_snapshot


def capture_tree_layout_snapshot(node_tree, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    sync_snapshot(snapshot, node_layout=collect_node_layout(node_tree))


def capture_node_layout_snapshot(node_tree, node, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    snapshot.node_layout[node.name] = node_layout_state(node)


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
