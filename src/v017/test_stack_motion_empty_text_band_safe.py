from src.v017.july22_frame_preflop_replay import (
    GEOMETRY,
    load_frame,
)
from src.v017.stack_motion_gate import (
    measure_stack_motion,
)


def main():
    before = load_frame(1)
    after = load_frame(2)

    print(
        "before_shape =",
        before.shape,
    )
    print(
        "after_shape =",
        after.shape,
    )

    # This exact two-frame call currently reaches an empty
    # text-band slice inside measure_stack_motion().
    #
    # Contract:
    # an empty optional text-band feature must never be passed
    # into native connected-components processing and must never
    # crash the interpreter.
    result = measure_stack_motion(
        before,
        after,
        GEOMETRY,
        "seat_top",
    )

    print(
        "result =",
        result,
    )

    print(
        "STACK MOTION EMPTY TEXT BAND: SAFE"
    )


if __name__ == "__main__":
    main()
