from __future__ import annotations


def _iter_bones(root_bones: list):
    stack = list(root_bones)
    seen = set()
    while stack:
        bone = stack.pop()
        if bone is None:
            continue
        if bone.name in seen:
            continue
        seen.add(bone.name)
        yield bone
        children = list(getattr(bone, "children", ()))
        for child in reversed(children):
            stack.append(child)


def _is_node_locked(node) -> bool:
    return bool(node is not None and getattr(node, "layout_locked", False))


def _arrange_reparented_nodes(
    root_bones: list,
    nodes,
    target_bone_names: set[str] | frozenset[str],
):
    default_node_height = 50.0
    x_step = 150.0
    if not target_bone_names:
        return

    bone_by_name = {bone.name: bone for bone in _iter_bones(root_bones)}
    targets_by_parent: dict[str | None, list[str]] = {}

    for bone_name in target_bone_names:
        bone = bone_by_name.get(bone_name)
        node = nodes.get(bone_name)
        if bone is None or node is None:
            continue
        if _is_node_locked(node):
            continue
        parent_name = bone.parent.name if bone.parent is not None else None
        targets_by_parent.setdefault(parent_name, []).append(bone_name)

    if not targets_by_parent:
        return

    root_names = [root.name for root in root_bones]

    for parent_name, target_names in targets_by_parent.items():
        # Preserve visual ordering by using current Y as baseline.
        target_names.sort(
            key=lambda name: float(nodes.get(name).location[1]) if nodes.get(name) is not None else 0.0,
            reverse=True,
        )

        if parent_name is None:
            sibling_y = []
            for root_name in root_names:
                if root_name in target_names:
                    continue
                root_node = nodes.get(root_name)
                if root_node is None:
                    continue
                sibling_y.append(float(root_node.location[1]))

            start_y = (min(sibling_y) - default_node_height) if sibling_y else 0.0
            for index, bone_name in enumerate(target_names):
                node = nodes.get(bone_name)
                if node is None:
                    continue
                node.location = (0.0, start_y - (index * default_node_height))
            continue

        parent_node = nodes.get(parent_name)
        if parent_node is None:
            continue

        parent_bone = bone_by_name.get(parent_name)
        sibling_y = []
        if parent_bone is not None:
            for child in parent_bone.children:
                if child.name in target_names:
                    continue
                child_node = nodes.get(child.name)
                if child_node is None:
                    continue
                sibling_y.append(float(child_node.location[1]))

        start_y = (min(sibling_y) - default_node_height) if sibling_y else float(parent_node.location[1])
        base_x = float(parent_node.location[0]) + x_step

        for index, bone_name in enumerate(target_names):
            node = nodes.get(bone_name)
            if node is None:
                continue
            node.location = (base_x, start_y - (index * default_node_height))


def _arrange_all_unlocked_nodes(root_bones: list, nodes):
    movable_height_map = {}
    default_node_height = 50
    x_step = 150

    def _node_of(bone):
        return nodes.get(bone.name)

    def _is_locked(bone) -> bool:
        return _is_node_locked(_node_of(bone))

    def calculate_movable_height(bone):
        child_heights = [calculate_movable_height(child) for child in bone.children]
        movable_children_height = sum(child_heights)

        if _is_locked(bone):
            result = movable_children_height
        elif movable_children_height > 0:
            result = movable_children_height
        else:
            result = default_node_height

        movable_height_map[bone.name] = result
        return result

    def layout_node(bone, x, y):
        node = _node_of(bone)
        if node is None:
            return

        is_locked = _is_locked(bone)
        if is_locked:
            anchor_x = float(node.location[0])
            anchor_y = float(node.location[1])
        else:
            node.location = (x, y)
            anchor_x = float(x)
            anchor_y = float(y)

        unlocked_children = [child for child in bone.children if not _is_locked(child)]
        total_unlocked_height = sum(movable_height_map[child.name] for child in unlocked_children)
        if total_unlocked_height > 0:
            start_y = anchor_y - (total_unlocked_height / 2)
            for child in unlocked_children:
                child_height = movable_height_map[child.name]
                child_y = start_y + (child_height / 2)
                layout_node(child, anchor_x + x_step, child_y)
                start_y += child_height

        # Recurse into locked children so only their unlocked descendants are rearranged.
        for child in bone.children:
            if not _is_locked(child):
                continue
            child_node = _node_of(child)
            if child_node is None:
                continue
            layout_node(child, float(child_node.location[0]), float(child_node.location[1]))

    for root_bone in root_bones:
        calculate_movable_height(root_bone)

    unlocked_roots = [root for root in root_bones if not _is_locked(root)]
    total_height = sum(movable_height_map[root.name] for root in unlocked_roots)
    start_y = total_height / 2

    for root_bone in unlocked_roots:
        subtree_height = movable_height_map[root_bone.name]
        if subtree_height <= 0:
            continue
        layout_node(root_bone, 0, start_y - (subtree_height / 2))
        start_y -= subtree_height

    # Keep locked roots fixed while still arranging their unlocked descendants.
    for root_bone in root_bones:
        if not _is_locked(root_bone):
            continue
        root_node = _node_of(root_bone)
        if root_node is None:
            continue
        layout_node(
            root_bone,
            float(root_node.location[0]),
            float(root_node.location[1]),
        )


def arrange_nodes(
    root_bones: list,
    nodes,
    *,
    target_bone_names: set[str] | frozenset[str] | None = None,
):
    if target_bone_names is not None:
        _arrange_reparented_nodes(root_bones, nodes, target_bone_names)
        return
    _arrange_all_unlocked_nodes(root_bones, nodes)
