from __future__ import annotations

from .constants import EDITOR_IDLE_SELECTION_SYNC_INTERVAL
from .selection_controller import sync_selection_state
from .services import armature_of, bone_node_tree_of
from .session import mark_tree_dirty, session_for_tree
from .sync import sync_tree_from_armature
from .topology_controller import apply_node_parent_link_edit


def sync_context_tree(
    context,
    *,
    should_arrange: bool = False,
    selection_only: bool = False,
    allow_fallback_selection: bool = False,
    origin: str = "unspecified",
):
    armature = armature_of(context)
    if armature is None:
        return None, None

    node_tree = bone_node_tree_of(context)
    if node_tree is None:
        return armature, None

    sync_bound_tree(
        context,
        armature,
        node_tree,
        should_arrange=should_arrange,
        selection_only=selection_only,
        allow_fallback_selection=allow_fallback_selection,
        origin=origin,
    )
    return armature, node_tree


def sync_bound_tree(
    context,
    armature,
    node_tree,
    *,
    should_arrange: bool = False,
    selection_only: bool = False,
    allow_fallback_selection: bool = False,
    origin: str = "unspecified",
):
    session = session_for_tree(node_tree)
    session.last_sync_origin = origin

    requested_flags = set()
    if selection_only:
        requested_flags.add("selection")
    if should_arrange:
        requested_flags.update({"topology", "selection", "layout"})

    if requested_flags:
        session.mark_dirty(*requested_flags)

    if not session.has_dirty() and allow_fallback_selection:
        if session.should_run_selection_fallback():
            session.mark_dirty("selection")

    if session.has_dirty("binding", "topology"):
        sync_tree_from_armature(
            context,
            armature,
            node_tree,
            should_arrange=should_arrange,
            snapshot=session.snapshot,
        )
        session.clear_dirty("binding", "topology", "selection", "layout")
        session.schedule_selection_fallback(EDITOR_IDLE_SELECTION_SYNC_INTERVAL)
        return node_tree

    if session.has_dirty("selection"):
        sync_selection_state(context, armature, node_tree, snapshot=session.snapshot)
        session.clear_dirty("selection")
        session.schedule_selection_fallback(EDITOR_IDLE_SELECTION_SYNC_INTERVAL)
        return node_tree

    if session.has_dirty("layout"):
        session.clear_dirty("layout")
        session.schedule_selection_fallback(EDITOR_IDLE_SELECTION_SYNC_INTERVAL)

    return node_tree


def apply_node_parent_edit(
    context,
    armature,
    node_tree,
    node,
    *,
    preferred_socket_name: str | None = None,
    origin: str = "node_edit",
):
    session = session_for_tree(node_tree)
    session.last_sync_origin = origin
    session.mark_dirty("topology", "selection")
    changed = apply_node_parent_link_edit(
        context,
        armature,
        node_tree,
        node,
        preferred_socket_name=preferred_socket_name,
    )
    session.clear_dirty("topology", "selection")
    return changed


def mark_context_tree_dirty(context, *flags: str):
    node_tree = bone_node_tree_of(context)
    mark_tree_dirty(node_tree, *flags)
    return node_tree


def mark_bound_tree_dirty(armature, *flags: str):
    from .binding import get_bound_tree

    node_tree = get_bound_tree(armature)
    mark_tree_dirty(node_tree, *flags)
    return node_tree


def mark_all_bound_trees_dirty(*flags: str):
    import bpy

    for armature in bpy.data.armatures:
        mark_bound_tree_dirty(armature, *flags)
