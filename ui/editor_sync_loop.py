import bpy
from bpy.types import Context

from ..controllers.sync_controller import mark_bound_tree_dirty, sync_bound_tree
from ..core.blender_context import current_context, temp_override_context
from ..core.constants import EDITOR_EVENT_SYNC_DELAY, EDITOR_SYNC_INTERVAL
from ..core.session import prune_tree_sessions, session_for_tree
from ..domain.snapshot_collectors import collect_topology_snapshot
from ..domain.services import armature_of, is_in_bone_node_tree
from ..domain.sync_common import bone_collection_for_context
from ..models.diff import diff_topology_state
from .editor_binding import active_editor_tree_for_armature
from .editor_registry import (
    iter_editor_contexts,
    prune_editor_states,
    update_editor_state,
)
from .hook_state import is_ui_hooks_registered


def _mark_fallback_sync_if_needed(context: Context, armature, session) -> bool:
    if not session.should_run_selection_fallback():
        return False

    bones = bone_collection_for_context(context, armature)
    topology_snapshot = collect_topology_snapshot(bones)
    topology_diff = diff_topology_state(session.snapshot, topology=topology_snapshot)
    if topology_diff.has_changes:
        session.mark_dirty("topology", "selection")
        return True

    session.mark_dirty("selection")
    return True


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

    node_tree = active_editor_tree_for_armature(context, armature)
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
        should_sync = _mark_fallback_sync_if_needed(context, armature, session)

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

    if bpy.app.timers.is_registered(run_event_driven_editor_sync):
        return

    bpy.app.timers.register(run_event_driven_editor_sync, first_interval=first_interval)


def run_event_driven_editor_sync():
    if not is_ui_hooks_registered():
        return None

    prune_tree_sessions()
    prune_editor_states()
    _sync_registered_editors(
        allow_fallback_selection=False,
        origin="event_bridge",
    )
    return None


def poll_active_editor_tree_sync():
    if not is_ui_hooks_registered():
        return None

    prune_tree_sessions()
    prune_editor_states()
    _sync_registered_editors(
        allow_fallback_selection=True,
        origin="ui_timer",
    )
    return EDITOR_SYNC_INTERVAL
