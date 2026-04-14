from __future__ import annotations

from ..models.snapshots import (
    BoneSelectionSnapshot,
    NodeLayoutState,
    NodeSelectionSnapshot,
    TopologySnapshot,
    TreeSyncSnapshot,
    sync_snapshot,
)


def collect_node_selection_snapshot(node_tree) -> NodeSelectionSnapshot:
    nodes = node_tree.nodes
    active_node = nodes.active
    return NodeSelectionSnapshot(
        active=active_node.name if active_node else None,
        active_select=bool(active_node and active_node.select),
        selected=frozenset(node.name for node in nodes if node.select),
    )


def collect_bone_selection_snapshot(bones) -> BoneSelectionSnapshot:
    return BoneSelectionSnapshot(
        active=bones.active.name if bones.active else None,
        selected=frozenset(bone.name for bone in bones if bone.select),
    )


def collect_topology_snapshot(bones) -> TopologySnapshot:
    return TopologySnapshot(
        signature=frozenset(
            (
                bone.name,
                bone.parent.name if bone.parent else None,
                bool(bone.parent and getattr(bone, "use_connect", False)),
            )
            for bone in bones
        )
    )


def node_layout_state(node) -> NodeLayoutState:
    return (float(node.location[0]), float(node.location[1])), float(node.width)


def collect_node_layout_snapshot(node_tree) -> dict[str, NodeLayoutState]:
    return {
        node.name: node_layout_state(node)
        for node in node_tree.nodes
    }


def sync_snapshot_from_tree(
    snapshot: TreeSyncSnapshot,
    node_tree,
    bones,
    topology: TopologySnapshot | None = None,
    *,
    capture_layout: bool = False,
):
    if topology is None:
        topology = collect_topology_snapshot(bones)

    sync_snapshot(
        snapshot,
        node_selection=collect_node_selection_snapshot(node_tree),
        bone_selection=collect_bone_selection_snapshot(bones),
        topology=topology,
        node_layout=collect_node_layout_snapshot(node_tree) if capture_layout else None,
    )
