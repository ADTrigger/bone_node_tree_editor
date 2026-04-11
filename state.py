class TreeSyncSnapshot:
    def __init__(self):
        self.active = None
        self.active_select = None
        self.selected = set()
        self.bone_active = None
        self.bone_selected = set()
        self.topology_signature = frozenset()
        self.node_layout = {}


_node_edit_lock = False
_ui_hooks_registered = False
_tree_sync_snapshots = {}


def is_node_edit_locked() -> bool:
    return _node_edit_lock


def set_node_edit_lock(state: bool):
    global _node_edit_lock
    _node_edit_lock = state


def is_ui_hooks_registered() -> bool:
    return _ui_hooks_registered


def set_ui_hooks_registered(state: bool):
    global _ui_hooks_registered
    _ui_hooks_registered = state


def snapshot_for_tree(node_tree) -> TreeSyncSnapshot:
    key = node_tree.as_pointer()
    snapshot = _tree_sync_snapshots.get(key)
    if snapshot is None:
        snapshot = TreeSyncSnapshot()
        _tree_sync_snapshots[key] = snapshot
    return snapshot


def clear_tree_snapshot(node_tree):
    _tree_sync_snapshots.pop(node_tree.as_pointer(), None)


def clear_all_tree_snapshots():
    _tree_sync_snapshots.clear()
