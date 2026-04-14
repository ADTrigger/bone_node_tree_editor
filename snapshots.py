from __future__ import annotations

from dataclasses import dataclass, field


TopologyEntry = tuple[str, str | None, bool]
NodeLayoutState = tuple[tuple[float, float], float]


@dataclass(frozen=True)
class NodeSelectionSnapshot:
    active: str | None = None
    active_select: bool = False
    selected: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class BoneSelectionSnapshot:
    active: str | None = None
    selected: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class TopologySnapshot:
    signature: frozenset[TopologyEntry] = field(default_factory=frozenset)


@dataclass
class TreeSyncSnapshot:
    active: str | None = None
    active_select: bool | None = None
    selected: set[str] = field(default_factory=set)
    bone_active: str | None = None
    bone_selected: set[str] = field(default_factory=set)
    topology_signature: frozenset[TopologyEntry] = field(default_factory=frozenset)
    node_layout: dict[str, NodeLayoutState] = field(default_factory=dict)


def node_selection_from_snapshot(snapshot: TreeSyncSnapshot) -> NodeSelectionSnapshot:
    return NodeSelectionSnapshot(
        active=snapshot.active,
        active_select=bool(snapshot.active_select),
        selected=frozenset(snapshot.selected),
    )


def bone_selection_from_snapshot(snapshot: TreeSyncSnapshot) -> BoneSelectionSnapshot:
    return BoneSelectionSnapshot(
        active=snapshot.bone_active,
        selected=frozenset(snapshot.bone_selected),
    )


def topology_from_snapshot(snapshot: TreeSyncSnapshot) -> TopologySnapshot:
    return TopologySnapshot(signature=frozenset(snapshot.topology_signature))


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


def sync_snapshot(
    snapshot: TreeSyncSnapshot,
    *,
    node_selection: NodeSelectionSnapshot | None = None,
    bone_selection: BoneSelectionSnapshot | None = None,
    topology: TopologySnapshot | None = None,
    node_layout: dict[str, NodeLayoutState] | None = None,
):
    if node_selection is not None:
        snapshot.active = node_selection.active
        snapshot.active_select = node_selection.active_select
        snapshot.selected = set(node_selection.selected)

    if bone_selection is not None:
        snapshot.bone_active = bone_selection.active
        snapshot.bone_selected = set(bone_selection.selected)

    if topology is not None:
        snapshot.topology_signature = frozenset(topology.signature)

    if node_layout is not None:
        snapshot.node_layout = dict(node_layout)


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
