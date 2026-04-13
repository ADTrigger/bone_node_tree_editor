import bpy


def current_context():
    return bpy.context


def fallback_context(context=None):
    if context is not None:
        return context
    return bpy.context


def mode_of(context=None) -> str | None:
    active_context = fallback_context(context)
    return getattr(active_context, "mode", None)


def is_mode(context, mode: str) -> bool:
    return mode_of(context) == mode


def is_object_mode(context=None) -> bool:
    return is_mode(context, "OBJECT")


def is_edit_armature_mode(context=None) -> bool:
    return is_mode(context, "EDIT_ARMATURE")


def active_theme(context=None):
    active_context = fallback_context(context)
    preferences = getattr(active_context, "preferences", None)
    if preferences is None:
        preferences = bpy.context.preferences

    themes = getattr(preferences, "themes", None)
    if not themes:
        return None
    return themes[0]


def set_active_vertex_group_by_name(obj, group_name: str | None):
    if obj is None:
        return

    vertex_groups = obj.vertex_groups
    if not group_name:
        vertex_groups.active_index = -1
        return

    group_index = vertex_groups.find(group_name)
    vertex_groups.active_index = group_index
