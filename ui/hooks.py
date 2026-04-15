import bpy
from bpy.types import Context

from ..core.constants import EDITOR_SYNC_INTERVAL, EDITOR_USE_POLLING_FALLBACK
from ..domain.services import is_in_bone_node_tree
from .editor_registry import clear_all_editor_states, remember_editor_context
from .editor_sync_loop import (
    is_ui_hooks_registered,
    poll_active_editor_tree_sync,
    request_editor_sync,
    run_event_driven_editor_sync,
    set_ui_hooks_registered,
)
from .operators import OT_SyncBoneNodeSelection, OT_UpdateBoneNodeTree


def _draw_pie(this: bpy.types.Menu, context: Context):
    if remember_editor_context(context):
        request_editor_sync()

    if is_in_bone_node_tree(context):
        pie = this.layout.menu_pie()
        pie.operator(OT_SyncBoneNodeSelection.bl_idname, icon="UV_SYNC_SELECT")
        pie.operator(OT_UpdateBoneNodeTree.bl_idname, icon="OUTLINER_DATA_ARMATURE")


def _draw_header_status(this, context: Context):
    if remember_editor_context(context):
        request_editor_sync()

    if not is_in_bone_node_tree(context):
        return

    if context.mode == "OBJECT":
        this.layout.label(text="test", icon="LOCKED")


def register_ui_hooks():
    if is_ui_hooks_registered():
        return

    set_ui_hooks_registered(True)
    clear_all_editor_states()
    bpy.types.NODE_MT_view_pie.append(_draw_pie)
    bpy.types.NODE_HT_header.append(_draw_header_status)
    if (
        EDITOR_USE_POLLING_FALLBACK
        and not bpy.app.timers.is_registered(poll_active_editor_tree_sync)
    ):
        bpy.app.timers.register(poll_active_editor_tree_sync, first_interval=EDITOR_SYNC_INTERVAL)
    request_editor_sync()


def unregister_ui_hooks():
    if not is_ui_hooks_registered():
        return

    set_ui_hooks_registered(False)
    clear_all_editor_states()
    bpy.types.NODE_MT_view_pie.remove(_draw_pie)
    bpy.types.NODE_HT_header.remove(_draw_header_status)
    if EDITOR_USE_POLLING_FALLBACK and bpy.app.timers.is_registered(poll_active_editor_tree_sync):
        bpy.app.timers.unregister(poll_active_editor_tree_sync)
    if bpy.app.timers.is_registered(run_event_driven_editor_sync):
        bpy.app.timers.unregister(run_event_driven_editor_sync)
