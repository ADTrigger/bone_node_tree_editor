import bpy
from bpy.types import Context

from .binding import ensure_bound_tree, get_bound_tree
from .constants import EDITOR_SYNC_INTERVAL
from .operators import OT_SyncBoneNodeSelection, OT_UpdateBoneNodeTree
from .services import armature_of, is_in_bone_node_tree
from .session import session_for_tree
from .state import is_ui_hooks_registered, set_ui_hooks_registered
from .sync_controller import mark_bound_tree_dirty, sync_bound_tree
from .ui_state import clear_all_editor_states, editor_key_for_space, prune_editor_states, update_editor_state


def _iter_node_editor_overrides():
    window_manager = getattr(bpy.context, "window_manager", None)
    if window_manager is None:
        return

    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue

        for area in screen.areas:
            if area.type != "NODE_EDITOR":
                continue

            space = area.spaces.active
            if space is None or space.type != "NODE_EDITOR":
                continue

            region = next((region for region in area.regions if region.type == "WINDOW"), None)
            if region is None:
                continue

            yield window, area, region, space


def _active_editor_tree_for_armature(context: Context, armature):
    space = context.space_data
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


def _poll_active_editor_tree_sync():
    if not is_ui_hooks_registered():
        return None

    active_editor_keys = set()
    for window, area, region, space in _iter_node_editor_overrides():
        active_editor_keys.add(editor_key_for_space(space))
        with bpy.context.temp_override(window=window, area=area, region=region, space_data=space):
            context = bpy.context
            if not is_in_bone_node_tree(context):
                update_editor_state(
                    space,
                    mode=getattr(context, "mode", None),
                    pinned=bool(getattr(space, "pin", False)),
                )
                continue

            armature = armature_of(context)
            if armature is None:
                update_editor_state(
                    space,
                    mode=getattr(context, "mode", None),
                    pinned=bool(getattr(space, "pin", False)),
                )
                continue

            node_tree = _active_editor_tree_for_armature(context, armature)
            if node_tree is None:
                update_editor_state(
                    space,
                    armature=armature,
                    mode=getattr(context, "mode", None),
                    pinned=bool(getattr(space, "pin", False)),
                )
                continue

            editor_changed = update_editor_state(
                space,
                armature=armature,
                node_tree=node_tree,
                mode=getattr(context, "mode", None),
                pinned=bool(getattr(space, "pin", False)),
            )
            if editor_changed:
                mark_bound_tree_dirty(armature, "binding", "selection")

            session = session_for_tree(node_tree)
            if not editor_changed and not session.has_dirty() and not session.should_run_selection_fallback():
                continue

            sync_bound_tree(
                context,
                armature,
                node_tree,
                allow_fallback_selection=True,
                origin="ui_timer",
            )

    prune_editor_states(active_editor_keys)
    return EDITOR_SYNC_INTERVAL


def _draw_pie(this: bpy.types.Menu, context: Context):
    if is_in_bone_node_tree(context):
        pie = this.layout.menu_pie()
        pie.operator(OT_SyncBoneNodeSelection.bl_idname, icon="UV_SYNC_SELECT")
        pie.operator(OT_UpdateBoneNodeTree.bl_idname, icon="OUTLINER_DATA_ARMATURE")


def _draw_header_status(this, context: Context):
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
        bpy.app.timers.register(_poll_active_editor_tree_sync, first_interval=0.0)


def unregister_ui_hooks():
    if not is_ui_hooks_registered():
        return

    set_ui_hooks_registered(False)
    clear_all_editor_states()
    bpy.types.NODE_MT_view_pie.remove(_draw_pie)
    bpy.types.NODE_HT_header.remove(_draw_header_status)
    if bpy.app.timers.is_registered(_poll_active_editor_tree_sync):
        bpy.app.timers.unregister(_poll_active_editor_tree_sync)
