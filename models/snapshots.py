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
