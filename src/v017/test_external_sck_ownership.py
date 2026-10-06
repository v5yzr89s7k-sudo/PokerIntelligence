from pathlib import Path
import ast


PATH = Path("src/v017/run_live_observer.py")
SOURCE = PATH.read_text()
TREE = ast.parse(SOURCE)


def function_source(name):
    for node in TREE.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return ast.get_source_segment(
                SOURCE,
                node,
            )

    raise AssertionError(
        f"missing function: {name}"
    )


start = function_source(
    "start_sck_capture"
)

stop = function_source(
    "stop_sck_capture"
)

external_start = start[
    start.index("if external_capture:"):
    start.index(
        "if _SCK_PROCESS is not None:",
        start.index("if external_capture:"),
    )
]

assert 'POKER_SCK_EXTERNAL' in start
assert "SCK_SOCKET.exists()" in external_start
assert "SCKFrameSource(" in external_start
assert "_SCK_FRAME_SOURCE.connect()" in external_start

# External ownership must never compile or spawn capture.
assert "build_sck_sampler()" not in external_start
assert "subprocess.Popen(" not in external_start
assert "SCK_BINARY" not in external_start
assert "SCK_HELPER_BINARY" not in external_start

# Shutdown must recognize external ownership and return
# without unlinking the host-owned socket.
external_stop_index = stop.index(
    'os.environ.get("POKER_SCK_EXTERNAL")'
)

unlink_index = stop.rfind(
    "SCK_SOCKET.unlink()"
)

assert external_stop_index >= 0
assert unlink_index > external_stop_index
assert "return" in stop[
    external_stop_index:
    unlink_index
]

print("EXTERNAL SCK SPAWN: ABSENT")
print("EXTERNAL SCK COMPILE: ABSENT")
print("EXTERNAL SOCKET CONSUMER: PRESENT")
print("EXTERNAL SOCKET OWNERSHIP: PRESERVED")
print("V0.17 EXTERNAL SCK OWNERSHIP: PASS")
