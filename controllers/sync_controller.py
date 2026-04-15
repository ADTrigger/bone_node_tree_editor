from __future__ import annotations

from ..core.constants import EDITOR_IDLE_SELECTION_SYNC_INTERVAL
from ..core.session import mark_tree_dirty, session_for_tree, snapshot_for_tree
from ..domain.snapshot_collectors import collect_topology_snapshot
from ..domain.services import armature_of, bone_collection_for_context, bone_node_tree_of
from ..models.diff import diff_topology_state
from .selection_controller import sync_selection_state
from .topology_controller import apply_node_parent_link_edit
from .topology_controller import (
    needs_tree_rebuild,
    rebuild_tree_from_armature,
    reconcile_tree_from_armature,
)


def sync_tree_from_armature(
    context,
    armature,
    node_tree,
    *,
    should_arrange: bool = False,
    snapshot=None,
):
    bones = bone_collection_for_context(context, armature)
    if snapshot is None:
        snapshot = snapshot_for_tree(node_tree)
    topology_snapshot = collect_topology_snapshot(bones)
    topology_diff = diff_topology_state(snapshot, topology=topology_snapshot)
    reparented_bone_names = set(topology_diff.reparented)
    reparented_bone_names.update(topology_diff.added)

    if should_arrange or topology_diff.has_changes:
        if needs_tree_rebuild(node_tree, bones=bones):
            rebuild_tree_from_armature(
                context,
                armature,
                node_tree,
                should_arrange=should_arrange,
                bones=bones,
                snapshot=snapshot,
                topology_snapshot=topology_snapshot,
                reparented_bone_names=reparented_bone_names if should_arrange else None,
            )
        else:
            reconcile_tree_from_armature(
                context,
                armature,
                node_tree,
                should_arrange=should_arrange,
                bones=bones,
                snapshot=snapshot,
                topology_snapshot=topology_snapshot,
                reparented_bone_names=reparented_bone_names if should_arrange else None,
            )
        return

    sync_selection_state(
        context,
        armature,
        node_tree,
        bones=bones,
        snapshot=snapshot,
        topology_snapshot=topology_snapshot,
    )


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
        bones = bone_collection_for_context(context, armature)
        topology_snapshot = collect_topology_snapshot(bones)
        topology_diff = diff_topology_state(session.snapshot, topology=topology_snapshot)

        # Some armature edits only surface as "selection" dirty signals.
        # Guard against missed topology dirties by probing topology before
        # running a selection-only sync.
        if topology_diff.has_changes:
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

        sync_selection_state(
            context,
            armature,
            node_tree,
            bones=bones,
            snapshot=session.snapshot,
            topology_snapshot=topology_snapshot,
        )
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
    if changed:
        mark_bound_tree_dirty(armature, "topology", "selection")
        from ..ui.editor_sync_loop import request_editor_sync

        request_editor_sync()
    return changed

def mark_bound_tree_dirty(armature, *flags: str):
    from ..core.binding import get_bound_tree

    node_tree = get_bound_tree(armature)
    mark_tree_dirty(node_tree, *flags)
    return node_tree


def mark_all_bound_trees_dirty(*flags: str):
    import bpy

    for armature in bpy.data.armatures:
        mark_bound_tree_dirty(armature, *flags)
