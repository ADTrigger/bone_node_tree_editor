import bpy
from bpy.types import Context

from .layout import arrange_nodes
from .services import set_bone_select, sync_bone_color_to_node
from .state import set_node_edit_lock, snapshot_for_tree


def _bone_collection_for_context(context: Context, armature):
    if context.mode == "EDIT_ARMATURE":
        return armature.edit_bones
    return armature.bones


def _bone_parent_state(bone):
    if bone is None or bone.parent is None:
        return None, False
    return bone.parent.name, bool(getattr(bone, "use_connect", False))


def _parent_socket_name(use_connect: bool) -> str:
    from .nodes import BoneNode

    if use_connect:
        return BoneNode.CONNECTED_PARENT_SOCKET_NAME
    return BoneNode.PARENT_SOCKET_NAME


def _collect_node_state(node_tree):
    nodes = node_tree.nodes
    active_node = nodes.active
    selected = {node.name for node in nodes if node.select}
    return active_node.name if active_node else None, bool(active_node and active_node.select), selected


def _node_layout_state(node):
    return (float(node.location[0]), float(node.location[1])), float(node.width)


def _collect_node_layout(node_tree):
    return {
        node.name: _node_layout_state(node)
        for node in node_tree.nodes
    }


def _collect_bone_state(bones):
    active = bones.active.name if bones.active else None
    selected = {bone.name for bone in bones if bone.select}
    return active, selected


def _collect_topology_signature(bones):
    return frozenset(
        (
            bone.name,
            bone.parent.name if bone.parent else None,
            bool(bone.parent and getattr(bone, "use_connect", False)),
        )
        for bone in bones
    )


def _sync_snapshot(snapshot, *, node_state=None, bone_state=None, topology_signature=None, node_layout=None):
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


def _sync_snapshot_from_tree(snapshot, node_tree, bones, topology_signature=None, *, capture_layout=False):
    if topology_signature is None:
        topology_signature = _collect_topology_signature(bones)

    _sync_snapshot(
        snapshot,
        node_state=_collect_node_state(node_tree),
        bone_state=_collect_bone_state(bones),
        topology_signature=topology_signature,
        node_layout=_collect_node_layout(node_tree) if capture_layout else None,
    )


def _sync_active_weight_group(context: Context, active_bone_name: str | None):
    if context.mode != "PAINT_WEIGHT" or context.object is None:
        return

    vertex_groups = context.object.vertex_groups
    if active_bone_name and vertex_groups.get(active_bone_name):
        bpy.ops.object.vertex_group_set_active(group=active_bone_name)
    else:
        vertex_groups.active_index = -1


def capture_tree_layout_snapshot(node_tree, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    _sync_snapshot(snapshot, node_layout=_collect_node_layout(node_tree))


def capture_node_layout_snapshot(node_tree, node, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    snapshot.node_layout[node.name] = _node_layout_state(node)


def restore_locked_tree_layout(node_tree, *, snapshot=None):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if not snapshot.node_layout:
        capture_tree_layout_snapshot(node_tree, snapshot=snapshot)
        return

    set_node_edit_lock(True)
    try:
        for node_name, ((x, y), width) in snapshot.node_layout.items():
            node = node_tree.nodes.get(node_name)
            if node is None:
                continue
            if tuple(node.location) != (x, y):
                node.location = (x, y)
            if node.width != width:
                node.width = width
    finally:
        set_node_edit_lock(False)


def normalize_parent_links(node_tree, node, preferred_socket_name: str | None = None):
    from .nodes import BoneNode

    socket_names = (
        BoneNode.PARENT_SOCKET_NAME,
        BoneNode.CONNECTED_PARENT_SOCKET_NAME,
    )
    links_by_socket = {
        socket_name: list(node.inputs[socket_name].links)
        for socket_name in socket_names
        if node.inputs.get(socket_name) is not None
    }

    keep_socket_name = None
    keep_link = None

    if preferred_socket_name in links_by_socket and links_by_socket[preferred_socket_name]:
        keep_socket_name = preferred_socket_name
        keep_link = links_by_socket[preferred_socket_name][-1]
    elif links_by_socket.get(BoneNode.CONNECTED_PARENT_SOCKET_NAME) and not links_by_socket.get(BoneNode.PARENT_SOCKET_NAME):
        keep_socket_name = BoneNode.CONNECTED_PARENT_SOCKET_NAME
        keep_link = links_by_socket[keep_socket_name][0]
    elif links_by_socket.get(BoneNode.PARENT_SOCKET_NAME) and not links_by_socket.get(BoneNode.CONNECTED_PARENT_SOCKET_NAME):
        keep_socket_name = BoneNode.PARENT_SOCKET_NAME
        keep_link = links_by_socket[keep_socket_name][0]
    elif links_by_socket.get(BoneNode.PARENT_SOCKET_NAME) or links_by_socket.get(BoneNode.CONNECTED_PARENT_SOCKET_NAME):
        default_socket_name = (
            BoneNode.CONNECTED_PARENT_SOCKET_NAME if node.is_connected_parent else BoneNode.PARENT_SOCKET_NAME
        )
        keep_socket_name = default_socket_name
        if not links_by_socket.get(keep_socket_name):
            keep_socket_name = (
                BoneNode.CONNECTED_PARENT_SOCKET_NAME
                if links_by_socket.get(BoneNode.CONNECTED_PARENT_SOCKET_NAME)
                else BoneNode.PARENT_SOCKET_NAME
            )
        keep_link = links_by_socket[keep_socket_name][0]

    removed_any = False
    for socket_name, links in links_by_socket.items():
        for link in list(links):
            should_keep = socket_name == keep_socket_name and link == keep_link
            if should_keep:
                continue
            node_tree.links.remove(link)
            removed_any = True

    return keep_socket_name, keep_link, removed_any


def normalized_parent_state(node_tree, node, preferred_socket_name: str | None = None):
    from .nodes import BoneNode

    keep_socket_name, keep_link, removed_any = normalize_parent_links(
        node_tree,
        node,
        preferred_socket_name=preferred_socket_name,
    )
    if keep_link is None:
        return None, False, None, removed_any

    if keep_link.is_muted or keep_link.from_node is None or keep_link.from_node == node:
        node_tree.links.remove(keep_link)
        return None, False, None, True

    is_connected_parent = keep_socket_name == BoneNode.CONNECTED_PARENT_SOCKET_NAME
    return keep_link.from_node.name, is_connected_parent, keep_link, removed_any


def apply_parent_link_change(context: Context, armature, node, parent_name: str | None, use_connect: bool):
    if context.mode != "EDIT_ARMATURE":
        return False

    bone = armature.edit_bones.get(node.name)
    if bone is None:
        return False

    bone_parent = armature.edit_bones.get(parent_name) if parent_name else None
    if bone_parent == bone:
        return False

    ancestor = bone_parent
    while ancestor:
        if ancestor == bone:
            return False
        ancestor = ancestor.parent

    set_node_edit_lock(True)
    try:
        bone.parent = bone_parent
        bone.use_connect = bool(bone_parent and use_connect)
        node.has_parent = bone_parent is not None
        node.is_connected_parent = bool(bone_parent and use_connect)
    finally:
        set_node_edit_lock(False)
    return True


def restore_node_parent_from_bone(node_tree, node, bone) -> bool:
    from .nodes import BoneNode

    parent_name, use_connect = _bone_parent_state(bone)
    preferred_socket_name = _parent_socket_name(use_connect) if parent_name else None
    current_parent_name, current_use_connect, _, removed_any = normalized_parent_state(
        node_tree,
        node,
        preferred_socket_name=preferred_socket_name,
    )
    current_use_connect = bool(current_parent_name and current_use_connect)
    expected_use_connect = bool(parent_name and use_connect)

    if (
        current_parent_name == parent_name
        and current_use_connect == expected_use_connect
        and not removed_any
    ):
        node.has_parent = parent_name is not None
        node.is_connected_parent = expected_use_connect
        return False

    socket_names = (
        BoneNode.PARENT_SOCKET_NAME,
        BoneNode.CONNECTED_PARENT_SOCKET_NAME,
    )
    set_node_edit_lock(True)
    try:
        for socket_name in socket_names:
            for link in list(node.inputs[socket_name].links):
                node_tree.links.remove(link)

        if parent_name:
            parent_node = node_tree.nodes.get(parent_name)
            if parent_node is not None:
                node_tree.links.new(
                    parent_node.outputs[BoneNode.CHILD_SOCKET_NAME],
                    node.inputs[_parent_socket_name(expected_use_connect)],
                )

        node.has_parent = parent_name is not None
        node.is_connected_parent = expected_use_connect
    finally:
        set_node_edit_lock(False)

    return True


def apply_node_parent_link_edit(
    context: Context,
    armature,
    node_tree,
    node,
    *,
    preferred_socket_name: str | None = None,
):
    bones = _bone_collection_for_context(context, armature)
    bone = bones.get(node.name)
    if bone is None:
        return False

    if context.mode != "EDIT_ARMATURE":
        return restore_node_parent_from_bone(node_tree, node, bone)

    parent_name, use_connect, _, removed_any = normalized_parent_state(
        node_tree,
        node,
        preferred_socket_name=preferred_socket_name,
    )
    use_connect = bool(parent_name and use_connect)

    current_parent_name, current_use_connect = _bone_parent_state(bone)
    current_use_connect = bool(current_parent_name and current_use_connect)

    if parent_name == current_parent_name and use_connect == current_use_connect:
        node.has_parent = parent_name is not None
        node.is_connected_parent = use_connect
        return removed_any

    if apply_parent_link_change(context, armature, node, parent_name, use_connect):
        return True

    restore_node_parent_from_bone(node_tree, node, bone)
    return False


def rebuild_tree_from_armature(
    context: Context,
    armature,
    node_tree,
    *,
    should_arrange: bool = True,
    capture_layout: bool = True,
    bones=None,
    snapshot=None,
    topology_signature=None,
):
    from .nodes import BoneNode

    if bones is None:
        bones = _bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_signature is None:
        topology_signature = _collect_topology_signature(bones)

    nodes = node_tree.nodes

    set_node_edit_lock(True)
    try:
        nodes.clear()
        node_tree.links.clear()

        for bone in bones:
            node = nodes.new(BoneNode.bl_idname)
            node.name = bone.name
            node.width = len(node.name) * 8
            node.select = bone.select
            node.has_parent = bone.parent is not None
            node.is_connected_parent = bool(bone.parent and getattr(bone, "use_connect", False))
            sync_bone_color_to_node(bone.color, node)
            if bones.active == bone:
                nodes.active = node

        root_bones = []
        for bone in bones:
            node = nodes.get(bone.name)
            if node is None:
                continue
            if bone.parent:
                parent_node = nodes.get(bone.parent.name)
                if parent_node:
                    socket_name = (
                        BoneNode.CONNECTED_PARENT_SOCKET_NAME
                        if getattr(bone, "use_connect", False)
                        else BoneNode.PARENT_SOCKET_NAME
                    )
                    node_tree.links.new(
                        parent_node.outputs[BoneNode.CHILD_SOCKET_NAME],
                        node.inputs[socket_name],
                    )
            else:
                root_bones.append(bone)
    finally:
        set_node_edit_lock(False)

    if should_arrange:
        arrange_nodes(root_bones, nodes)

    _sync_snapshot_from_tree(
        snapshot,
        node_tree,
        bones,
        topology_signature,
        capture_layout=capture_layout,
    )


def reconcile_tree_from_armature(
    context: Context,
    armature,
    node_tree,
    *,
    should_arrange: bool = False,
    capture_layout: bool = True,
    bones=None,
    snapshot=None,
    topology_signature=None,
):
    from .nodes import BoneNode

    if bones is None:
        bones = _bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_signature is None:
        topology_signature = _collect_topology_signature(bones)

    nodes = node_tree.nodes
    bone_names = {bone.name for bone in bones}

    set_node_edit_lock(True)
    try:
        for node in list(nodes):
            if node.name not in bone_names:
                nodes.remove(node)

        for bone in bones:
            node = nodes.get(bone.name)
            if node is None:
                node = nodes.new(BoneNode.bl_idname)
                node.name = bone.name
                node.width = len(node.name) * 8
            node.select = bone.select
            node.has_parent = bone.parent is not None
            node.is_connected_parent = bool(bone.parent and getattr(bone, "use_connect", False))
            sync_bone_color_to_node(bone.color, node)
            if bones.active == bone:
                nodes.active = node

        if bones.active is None:
            nodes.active = None

        expected_links = set()
        expected_socket_by_child = {}
        for bone in bones:
            if bone.parent is None:
                continue
            socket_name = (
                BoneNode.CONNECTED_PARENT_SOCKET_NAME
                if getattr(bone, "use_connect", False)
                else BoneNode.PARENT_SOCKET_NAME
            )
            expected_links.add((bone.parent.name, bone.name, socket_name))
            expected_socket_by_child[bone.name] = socket_name

        for link in list(node_tree.links):
            if (
                link.from_node is None
                or link.to_node is None
                or link.to_socket is None
                or (link.from_node.name, link.to_node.name, link.to_socket.name) not in expected_links
            ):
                node_tree.links.remove(link)

        existing_links = {
            (link.from_node.name, link.to_node.name, link.to_socket.name)
            for link in node_tree.links
            if link.from_node and link.to_node and link.to_socket
        }
        for parent_name, child_name, socket_name in expected_links - existing_links:
            parent_node = nodes.get(parent_name)
            child_node = nodes.get(child_name)
            if parent_node and child_node:
                node_tree.links.new(
                    parent_node.outputs[BoneNode.CHILD_SOCKET_NAME],
                    child_node.inputs[socket_name],
                )

        for bone in bones:
            node = nodes.get(bone.name)
            if node is None:
                continue
            normalize_parent_links(
                node_tree,
                node,
                preferred_socket_name=expected_socket_by_child.get(bone.name),
            )
    finally:
        set_node_edit_lock(False)

    if should_arrange:
        root_bones = [bone for bone in bones if bone.parent is None]
        arrange_nodes(root_bones, nodes)

    _sync_snapshot_from_tree(
        snapshot,
        node_tree,
        bones,
        topology_signature,
        capture_layout=capture_layout,
    )


def sync_node_selection_to_bone(
    context: Context,
    bones,
    node_tree,
    *,
    node_state=None,
    bone_state=None,
    snapshot=None,
    topology_signature=None,
):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if node_state is None:
        node_state = _collect_node_state(node_tree)
    if bone_state is None:
        bone_state = _collect_bone_state(bones)

    node_active, node_active_select, node_selected = node_state
    _, bone_selected = bone_state

    valid_selected_bones = {bone_name for bone_name in node_selected if bones.get(bone_name) is not None}

    for bone_name in bone_selected - valid_selected_bones:
        bone = bones.get(bone_name)
        if bone is not None:
            set_bone_select(bone, False)

    for bone_name in valid_selected_bones - bone_selected:
        bone = bones.get(bone_name)
        if bone is not None:
            set_bone_select(bone, True)

    active_bone = None
    if node_active_select and node_active:
        active_bone = bones.get(node_active)

    if bones.active != active_bone:
        bones.active = active_bone

    active_bone_name = active_bone.name if active_bone else None
    if active_bone is not None:
        set_bone_select(active_bone, True)

    _sync_active_weight_group(context, active_bone_name)
    _sync_snapshot(
        snapshot,
        node_state=node_state,
        bone_state=(active_bone_name, valid_selected_bones),
        topology_signature=topology_signature,
    )


def sync_bone_selection_to_node(
    bones,
    node_tree,
    *,
    node_state=None,
    bone_state=None,
    snapshot=None,
    topology_signature=None,
):
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)

    nodes = node_tree.nodes
    if bone_state is None:
        bone_state = _collect_bone_state(bones)
    if node_state is None:
        node_state = _collect_node_state(node_tree)

    bone_active, bone_selected = bone_state
    node_active, _, node_selected = node_state

    valid_selected_nodes = {node_name for node_name in bone_selected if nodes.get(node_name) is not None}

    for node_name in node_selected - valid_selected_nodes:
        node = nodes.get(node_name)
        if node is not None:
            node.select = False

    for node_name in valid_selected_nodes - node_selected:
        node = nodes.get(node_name)
        if node is not None:
            node.select = True

    active_node = nodes.get(bone_active) if bone_active else None
    if node_active != (active_node.name if active_node else None):
        nodes.active = active_node

    active_node_name = active_node.name if active_node else None
    active_node_select = bool(active_node and active_node.select)
    _sync_snapshot(
        snapshot,
        node_state=(active_node_name, active_node_select, valid_selected_nodes),
        bone_state=bone_state,
        topology_signature=topology_signature,
    )


def sync_selection_state(
    context: Context,
    armature,
    node_tree,
    *,
    bones=None,
    snapshot=None,
    topology_signature=None,
):
    if bones is None:
        bones = _bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_signature is None:
        topology_signature = _collect_topology_signature(bones)

    node_state = _collect_node_state(node_tree)
    bone_state = _collect_bone_state(bones)
    node_active, node_active_select, node_selected = node_state
    bone_active, bone_selected = bone_state

    node_changed = (
        snapshot.active != node_active
        or snapshot.active_select != node_active_select
        or snapshot.selected != node_selected
    )
    bone_changed = (
        snapshot.bone_active != bone_active
        or snapshot.bone_selected != bone_selected
    )

    if not node_changed and not bone_changed:
        if snapshot.topology_signature != topology_signature:
            _sync_snapshot(snapshot, topology_signature=topology_signature)
        return

    if bone_changed and not node_changed:
        sync_bone_selection_to_node(
            bones,
            node_tree,
            node_state=node_state,
            bone_state=bone_state,
            snapshot=snapshot,
            topology_signature=topology_signature,
        )
        return

    sync_node_selection_to_bone(
        context,
        bones,
        node_tree,
        node_state=node_state,
        bone_state=bone_state,
        snapshot=snapshot,
        topology_signature=topology_signature,
    )


def sync_tree_from_armature(context: Context, armature, node_tree):
    bones = _bone_collection_for_context(context, armature)
    snapshot = snapshot_for_tree(node_tree)
    topology_signature = _collect_topology_signature(bones)

    if snapshot.topology_signature != topology_signature:
        reconcile_tree_from_armature(
            context,
            armature,
            node_tree,
            should_arrange=False,
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
