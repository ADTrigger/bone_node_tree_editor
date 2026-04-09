class NodeTreeSnapshot:
    def __init__(self):
        self.active = None
        self.active_select = None
        self.selected = {}
        self.handler = None
        self.region = "HEADER"


_node_edit_lock = False
old_node_tree_snapshot = NodeTreeSnapshot()


def is_node_edit_locked() -> bool:
    return _node_edit_lock


def set_node_edit_lock(state: bool):
    global _node_edit_lock
    _node_edit_lock = state
