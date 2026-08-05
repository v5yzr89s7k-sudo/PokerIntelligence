from src.vision.stack_reader import _resolve


def resolve(green, plain, otsu):
    return _resolve([
        {
            "variant": "green",
            "raw": str(green),
            "stack_bb": green,
        },
        {
            "variant": "plain",
            "raw": str(plain),
            "stack_bb": plain,
        },
        {
            "variant": "otsu",
            "raw": str(otsu),
            "stack_bb": otsu,
        },
    ])


value, votes = resolve(
    99.98,
    55.58,
    55.58,
)

assert value == 55.58
assert votes == 2

value, votes = resolve(
    82.29,
    32.29,
    32.29,
)

assert value == 32.29
assert votes == 2

value, votes = resolve(
    47.25,
    47.25,
    47.25,
)

assert value == 47.25
assert votes == 3

print("Stack reader majority regressions passed.")
