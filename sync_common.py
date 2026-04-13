def bone_collection_for_context(context, armature):
    if context.mode == "EDIT_ARMATURE":
        return armature.edit_bones
    return armature.bones


def bone_parent_state(bone):
    if bone is None or bone.parent is None:
        return None, False
    return bone.parent.name, bool(getattr(bone, "use_connect", False))


def parent_socket_name(use_connect: bool) -> str:
    from .nodes import BoneNode

    if use_connect:
        return BoneNode.CONNECTED_PARENT_SOCKET_NAME
    return BoneNode.PARENT_SOCKET_NAME


def collect_node_state(node_tree):
    nodes = node_tree.nodes
    active_node = nodes.active
    selected = {node.name for node in nodes if node.select}
    return active_node.name if active_node else None, bool(active_node and active_node.select), selected


def node_layout_state(node):
    return (float(node.location[0]), float(node.location[1])), float(node.width)


def collect_node_layout(node_tree):
    return {
        node.name: node_layout_state(node)
        for node in node_tree.nodes
    }


def collect_bone_state(bones):
    active = bones.active.name if bones.active else None
    selected = {bone.name for bone in bones if bone.select}
    return active, selected


def collect_topology_signature(bones):
    return frozenset(
        (
            bone.name,
            bone.parent.name if bone.parent else None,
            bool(bone.parent and getattr(bone, "use_connect", False)),
        )
        for bone in bones
    )


def sync_snapshot(snapshot, *, node_state=None, bone_state=None, topology_signature=None, node_layout=None):
    if node_state is not None:
        active, active_select, selected = node_state
        snapshot.active = active
        snapshot.active_select = active_select
        snapshot.selected = set(selected)

    if bone_state is not None:
        active, selected = bone_state
        snapshot.bone_active = active
        snapshot.bone_selected = set(selected)

    if topology_signature is not None:
        snapshot.topology_signature = frozenset(topology_signature)

    if node_layout is not None:
        snapshot.node_layout = dict(node_layout)


def sync_snapshot_from_tree(snapshot, node_tree, bones, topology_signature=None, *, capture_layout=False):
    if topology_signature is None:
        topology_signature = collect_topology_signature(bones)

    sync_snapshot(
        snapshot,
        node_state=collect_node_state(node_tree),
        bone_state=collect_bone_state(bones),
        topology_signature=topology_signature,
        node_layout=collect_node_layout(node_tree) if capture_layout else None,
    )
