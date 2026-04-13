import bpy
from bpy.app.handlers import persistent

from .session import clear_all_tree_sessions
from .sync_controller import mark_all_bound_trees_dirty, mark_bound_tree_dirty


def _iter_updated_armatures(depsgraph):
    armature_flags = {}
    for update in getattr(depsgraph, "updates", ()):
        id_data = getattr(update, "id", None)
        if id_data is None:
            continue

        original = getattr(id_data, "original", None)
        if original is not None:
            id_data = original

        armature = None
        if isinstance(id_data, bpy.types.Armature):
            armature = id_data
            flags = ("topology", "selection")
        elif isinstance(id_data, bpy.types.Object) and getattr(id_data, "type", None) == "ARMATURE":
            armature = id_data.data
            flags = ("selection",)
        else:
            continue

        key = int(armature.as_pointer())
        entry = armature_flags.get(key)
        if entry is None:
            armature_flags[key] = (armature, set(flags))
            continue

        _, merged_flags = entry
        merged_flags.update(flags)

    for armature, flags in armature_flags.values():
        yield armature, tuple(sorted(flags))


@persistent
def _on_depsgraph_update_post(scene, depsgraph):
    del scene
    for armature, flags in _iter_updated_armatures(depsgraph):
        mark_bound_tree_dirty(armature, *flags)


@persistent
def _on_undo_post(_dummy):
    clear_all_tree_sessions()
    mark_all_bound_trees_dirty("topology", "selection")


@persistent
def _on_redo_post(_dummy):
    clear_all_tree_sessions()
    mark_all_bound_trees_dirty("topology", "selection")


@persistent
def _on_load_post(_dummy):
    clear_all_tree_sessions()
    mark_all_bound_trees_dirty("binding", "topology", "selection")


def _append_handler(handler_list, callback):
    if handler_list is None:
        return
    if callback not in handler_list:
        handler_list.append(callback)


def _remove_handler(handler_list, callback):
    if handler_list is None:
        return
    while callback in handler_list:
        handler_list.remove(callback)


def register_event_hooks():
    handlers = bpy.app.handlers
    _append_handler(getattr(handlers, "depsgraph_update_post", None), _on_depsgraph_update_post)
    _append_handler(getattr(handlers, "undo_post", None), _on_undo_post)
    _append_handler(getattr(handlers, "redo_post", None), _on_redo_post)
    _append_handler(getattr(handlers, "load_post", None), _on_load_post)
    mark_all_bound_trees_dirty("binding", "topology", "selection")


def unregister_event_hooks():
    handlers = bpy.app.handlers
    _remove_handler(getattr(handlers, "depsgraph_update_post", None), _on_depsgraph_update_post)
    _remove_handler(getattr(handlers, "undo_post", None), _on_undo_post)
    _remove_handler(getattr(handlers, "redo_post", None), _on_redo_post)
    _remove_handler(getattr(handlers, "load_post", None), _on_load_post)
