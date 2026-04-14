bl_info = {
    "name": "Bone Node Tree Editor 🦴",
    # "description": "",
    "author": "Starfelll",
    "version": (1, 2, 0),
    "blender": (4, 5, 0),
    # "location": "View3D > Add > Mesh",
    "doc_url": "https://www.bilibili.com/video/BV15AqjYiE2Y",
    # "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Node",
}

import bpy

from .core.binding import clear_binding_runtime_state
from .core.migration import migrate_all_data
from .core.session import clear_all_tree_sessions
from .events.event_bridge import register_event_hooks, unregister_event_hooks
from .ui.nodes import BoneNodeTree, BoneNode
from .ui.operators import OT_UpdateBoneNodeTree, OT_SyncBoneNodeSelection
from .ui.ui import register_ui_hooks, unregister_ui_hooks


classes = [
    BoneNodeTree,
    BoneNode,
    OT_UpdateBoneNodeTree,
    OT_SyncBoneNodeSelection,
]


def register():
    clear_all_tree_sessions()
    for cls in classes:
        bpy.utils.register_class(cls)
    migrate_all_data()
    register_event_hooks()
    register_ui_hooks()


def unregister():
    unregister_ui_hooks()
    unregister_event_hooks()
    clear_all_tree_sessions()
    clear_binding_runtime_state()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
