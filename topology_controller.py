from bpy.types import Context

from .layout import arrange_nodes
from .services import sync_bone_color_to_node
from .session import snapshot_for_tree, tree_mutation
from .sync_common import (
    bone_collection_for_context,
    bone_parent_state,
    collect_topology_signature,
    parent_socket_name,
    sync_snapshot_from_tree,
)


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

    with tree_mutation(node.id_data, origin="apply_parent_link_change"):
        bone.parent = bone_parent
        bone.use_connect = bool(bone_parent and use_connect)
        node.has_parent = bone_parent is not None
        node.is_connected_parent = bool(bone_parent and use_connect)
    return True


def restore_node_parent_from_bone(node_tree, node, bone) -> bool:
    from .nodes import BoneNode

    parent_name, use_connect = bone_parent_state(bone)
    preferred_socket_name = parent_socket_name(use_connect) if parent_name else None
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
    with tree_mutation(node_tree, origin="restore_node_parent_from_bone"):
        for socket_name in socket_names:
            for link in list(node.inputs[socket_name].links):
                node_tree.links.remove(link)

        if parent_name:
            parent_node = node_tree.nodes.get(parent_name)
            if parent_node is not None:
                node_tree.links.new(
                    parent_node.outputs[BoneNode.CHILD_SOCKET_NAME],
                    node.inputs[parent_socket_name(expected_use_connect)],
                )

        node.has_parent = parent_name is not None
        node.is_connected_parent = expected_use_connect

    return True


def apply_node_parent_link_edit(
    context: Context,
    armature,
    node_tree,
    node,
    *,
    preferred_socket_name: str | None = None,
):
    bones = bone_collection_for_context(context, armature)
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

    current_parent_name, current_use_connect = bone_parent_state(bone)
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
        bones = bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_signature is None:
        topology_signature = collect_topology_signature(bones)

    nodes = node_tree.nodes

    with tree_mutation(node_tree, origin="rebuild_tree_from_armature"):
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

    if should_arrange:
        arrange_nodes(root_bones, nodes)

    sync_snapshot_from_tree(
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
        bones = bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    if topology_signature is None:
        topology_signature = collect_topology_signature(bones)

    nodes = node_tree.nodes
    bone_names = {bone.name for bone in bones}

    with tree_mutation(node_tree, origin="reconcile_tree_from_armature"):
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

    if should_arrange:
        root_bones = [bone for bone in bones if bone.parent is None]
        arrange_nodes(root_bones, nodes)

    sync_snapshot_from_tree(
        snapshot,
        node_tree,
        bones,
        topology_signature,
        capture_layout=capture_layout,
    )
