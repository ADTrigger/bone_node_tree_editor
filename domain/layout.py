def arrange_nodes(root_bones: list, nodes):
    subtree_height_map = {}
    default_node_height = 50

    def calculate_subtree_height(bone):
        if not bone.children:
            result = default_node_height
        else:
            result = sum(calculate_subtree_height(child) for child in bone.children)
        subtree_height_map[bone.name] = result
        return result

    def layout_node(bone, x, y):
        node = nodes.get(bone.name)
        if node is None:
            return

        node.location = (x, y)
        total_height = sum(subtree_height_map[child.name] for child in bone.children)
        if total_height == 0:
            return

        start_y = y - (total_height / 2)
        for child in bone.children:
            child_height = subtree_height_map[child.name]
            layout_node(child, x + 150, start_y + (child_height / 2))
            start_y += child_height

    total_height = sum(calculate_subtree_height(root_bone) for root_bone in root_bones)
    start_y = total_height / 2
    for root_bone in root_bones:
        subtree_height = subtree_height_map[root_bone.name]
        layout_node(root_bone, 0, start_y - (subtree_height / 2))
        start_y -= subtree_height
