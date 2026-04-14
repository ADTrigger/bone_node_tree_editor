from __future__ import annotations

from dataclasses import dataclass, field

from .snapshots import (
    BoneSelectionSnapshot,
    NodeSelectionSnapshot,
    TopologySnapshot,
    TreeSyncSnapshot,
    bone_selection_from_snapshot,
    node_selection_from_snapshot,
    topology_from_snapshot,
)


@dataclass(frozen=True)
class SelectionDiff:
    node_selection: NodeSelectionSnapshot = field(default_factory=NodeSelectionSnapshot)
    bone_selection: BoneSelectionSnapshot = field(default_factory=BoneSelectionSnapshot)
    node_changed: bool = False
    bone_changed: bool = False
    topology_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return self.node_changed or self.bone_changed

    @property
    def should_sync_bone_to_node(self) -> bool:
        return self.bone_changed and not self.node_changed

    @property
    def should_sync_node_to_bone(self) -> bool:
        return self.node_changed


@dataclass(frozen=True)
class TopologyDiff:
    previous: TopologySnapshot = field(default_factory=TopologySnapshot)
    current: TopologySnapshot = field(default_factory=TopologySnapshot)
    added: frozenset[str] = field(default_factory=frozenset)
    removed: frozenset[str] = field(default_factory=frozenset)
    reparented: frozenset[str] = field(default_factory=frozenset)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.reparented)


def _topology_map(topology: TopologySnapshot) -> dict[str, tuple[str | None, bool]]:
    return {
        bone_name: (parent_name, use_connect)
        for bone_name, parent_name, use_connect in topology.signature
    }


def diff_selection_state(
    snapshot: TreeSyncSnapshot,
    *,
    node_selection: NodeSelectionSnapshot,
    bone_selection: BoneSelectionSnapshot,
    topology: TopologySnapshot,
) -> SelectionDiff:
    previous_node = node_selection_from_snapshot(snapshot)
    previous_bone = bone_selection_from_snapshot(snapshot)
    previous_topology = topology_from_snapshot(snapshot)
    return SelectionDiff(
        node_selection=node_selection,
        bone_selection=bone_selection,
        node_changed=previous_node != node_selection,
        bone_changed=previous_bone != bone_selection,
        topology_changed=previous_topology != topology,
    )


def diff_topology_state(
    snapshot: TreeSyncSnapshot,
    *,
    topology: TopologySnapshot,
) -> TopologyDiff:
    previous = topology_from_snapshot(snapshot)
    previous_map = _topology_map(previous)
    current_map = _topology_map(topology)
    previous_names = frozenset(previous_map)
    current_names = frozenset(current_map)
    shared_names = previous_names & current_names
    return TopologyDiff(
        previous=previous,
        current=topology,
        added=current_names - previous_names,
        removed=previous_names - current_names,
        reparented=frozenset(
            bone_name
            for bone_name in shared_names
            if previous_map[bone_name] != current_map[bone_name]
        ),
    )
