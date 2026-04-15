import bpy
from contextlib import contextmanager


def current_context():
    return bpy.context


def _active_context(context=None):
    if context is not None:
        return context
    return bpy.context


def is_object_mode(context=None) -> bool:
    return getattr(_active_context(context), "mode", None) == "OBJECT"


def is_edit_armature_mode(context=None) -> bool:
    return getattr(_active_context(context), "mode", None) == "EDIT_ARMATURE"


def set_active_vertex_group_by_name(obj, group_name: str | None):
    if obj is None:
        return

    vertex_groups = obj.vertex_groups
    if not group_name:
        vertex_groups.active_index = -1
        return

    group_index = vertex_groups.find(group_name)
    vertex_groups.active_index = group_index


def object_of(context=None):
    return getattr(_active_context(context), "object", None)


def active_object_of(context=None):
    return getattr(_active_context(context), "active_object", None)


def pose_object_of(context=None):
    return getattr(_active_context(context), "pose_object", None)


def selected_objects_of(context=None):
    selected_objects = getattr(_active_context(context), "selected_objects", None)
    if selected_objects is None:
        return ()
    return tuple(selected_objects)


def view_layer_active_object_of(context=None):
    view_layer = getattr(_active_context(context), "view_layer", None)
    if view_layer is None:
        return None
    objects = getattr(view_layer, "objects", None)
    if objects is None:
        return None
    return getattr(objects, "active", None)


def space_data_of(context=None):
    return getattr(_active_context(context), "space_data", None)


@contextmanager
def temp_override_context(*, window, area, region, space_data):
    with bpy.context.temp_override(window=window, area=area, region=region, space_data=space_data):
        yield bpy.context
