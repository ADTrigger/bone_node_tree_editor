PARENT_SOCKET_NAME = "Parent"
CONNECTED_PARENT_SOCKET_NAME = "Connected Parent"
CHILD_SOCKET_NAME = "Child Of"
CHILD_OUTPUT_SPACER_IDENTIFIER = "_bnte_child_output_spacer"

PARENT_INPUT_SOCKET_NAMES = (
    PARENT_SOCKET_NAME,
    CONNECTED_PARENT_SOCKET_NAME,
)


def parent_socket_name(use_connect: bool) -> str:
    if use_connect:
        return CONNECTED_PARENT_SOCKET_NAME
    return PARENT_SOCKET_NAME
