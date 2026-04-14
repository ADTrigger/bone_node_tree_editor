import bpy
from bpy.types import Context

from ..controllers.sync_controller import mark_bound_tree_dirty, sync_bound_tree
from ..core.blender_context import current_context, space_data_of, temp_override_context
from ..core.binding import ensure_bound_tree, get_bound_tree
from ..core.constants import EDITOR_EVENT_SYNC_DELAY, EDITOR_SYNC_INTERVAL
from ..core.session import prune_tree_sessions, session_for_tree
from ..core.state import is_ui_hooks_registered, set_ui_hooks_registered
from ..domain.services import armature_of, is_in_bone_node_tree
from .operators import OT_SyncBoneNodeSelection, OT_UpdateBoneNodeTree
from .ui_state import (
    clear_all_editor_states,
    iter_editor_contexts,
    prune_editor_states,
    remember_editor_context,
    update_editor_state,
)


def _active_editor_tree_for_armature(context: Context, armature):
    space = space_data_of(context)
    if space is None or space.type != "NODE_EDITOR":
        return None

    bound_tree = get_bound_tree(armature)
    current_tree = getattr(space, "edit_tree", None)

    # Respect pinned editors so we do not override intentionally fixed tree views.
    if getattr(space, "pin", False):
        if bound_tree is None or current_tree != bound_tree:
            return None
        return bound_tree

    if bound_tree is None:
        bound_tree = ensure_bound_tree(armature)

    if current_tree != bound_tree:
        space.node_tree = bound_tree
        mark_bound_tree_dirty(armature, "binding", "selection")

    return bound_tree


def _sync_registered_editor(
    context: Context,
    *,
    window,
    area,
    region,
    space,
    allow_fallback_selection: bool,
    origin: str,
):
    if not is_in_bone_node_tree(context):
        update_editor_state(
            space,
            window=window,
            area=area,
            region=region,
            mode=getattr(context, "mode", None),
            pinned=bool(getattr(space, "pin", False)),
        )
        return False

    armature = armature_of(context)
    if armature is None:
        update_editor_state(
            space,
            window=window,
            area=area,
            region=region,
            mode=getattr(context, "mode", None),
            pinned=bool(getattr(space, "pin", False)),
        )
        return False

    node_tree = _active_editor_tree_for_armature(context, armature)
    if node_tree is None:
        update_editor_state(
            space,
            window=window,
            area=area,
            region=region,
            armature=armature,
            mode=getattr(context, "mode", None),
            pinned=bool(getattr(space, "pin", False)),
        )
        return False

    editor_changed = update_editor_state(
        space,
        window=window,
        area=area,
        region=region,
        armature=armature,
        node_tree=node_tree,
        mode=getattr(context, "mode", None),
        pinned=bool(getattr(space, "pin", False)),
    )
    if editor_changed:
        mark_bound_tree_dirty(armature, "binding", "selection")

    session = session_for_tree(node_tree)
    should_sync = editor_changed or session.has_dirty()
    if not should_sync and allow_fallback_selection:
        should_sync = session.should_run_selection_fallback()

    if not should_sync:
        return False

    sync_bound_tree(
        context,
        armature,
        node_tree,
        allow_fallback_selection=allow_fallback_selection,
        origin=origin,
    )
    return True


def _sync_registered_editors(*, allow_fallback_selection: bool, origin: str):
    synced_any = False
    for window, area, region, space in iter_editor_contexts():
        with temp_override_context(window=window, area=area, region=region, space_data=space):
            context = current_context()
            if _sync_registered_editor(
                context,
                window=window,
                area=area,
                region=region,
                space=space,
                allow_fallback_selection=allow_fallback_selection,
                origin=origin,
            ):
                synced_any = True
    return synced_any


def request_editor_sync(*, first_interval: float = EDITOR_EVENT_SYNC_DELAY):
    if not is_ui_hooks_registered():
        return

    if bpy.app.timers.is_registered(_run_event_driven_editor_sync):
        return

    bpy.app.timers.register(_run_event_driven_editor_sync, first_interval=first_interval)


def _run_event_driven_editor_sync():
    if not is_ui_hooks_registered():
        return None

    prune_tree_sessions()
    prune_editor_states()
    _sync_registered_editors(
        allow_fallback_selection=False,
        origin="event_bridge",
    )
    return None


def _poll_active_editor_tree_sync():
    if not is_ui_hooks_registered():
        return None

    prune_tree_sessions()
    prune_editor_states()
    _sync_registered_editors(
        allow_fallback_selection=True,
        origin="ui_timer",
    )
    return EDITOR_SYNC_INTERVAL


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
        this.layout.label(text="Object 模式下节点图已锁定", icon="LOCKED")


def register_ui_hooks():
    if is_ui_hooks_registered():
        return

    set_ui_hooks_registered(True)
    clear_all_editor_states()
    bpy.types.NODE_MT_view_pie.append(_draw_pie)
    bpy.types.NODE_HT_header.append(_draw_header_status)
    if not bpy.app.timers.is_registered(_poll_active_editor_tree_sync):
        bpy.app.timers.register(_poll_active_editor_tree_sync, first_interval=EDITOR_SYNC_INTERVAL)
    request_editor_sync()


def unregister_ui_hooks():
    if not is_ui_hooks_registered():
        return

    set_ui_hooks_registered(False)
    clear_all_editor_states()
    bpy.types.NODE_MT_view_pie.remove(_draw_pie)
    bpy.types.NODE_HT_header.remove(_draw_header_status)
    if bpy.app.timers.is_registered(_poll_active_editor_tree_sync):
        bpy.app.timers.unregister(_poll_active_editor_tree_sync)
    if bpy.app.timers.is_registered(_run_event_driven_editor_sync):
        bpy.app.timers.unregister(_run_event_driven_editor_sync)
