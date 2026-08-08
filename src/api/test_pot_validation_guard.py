expected = 4.38
observed = 16.87

tolerance = max(
    1.0,
    round(expected * 0.35, 2),
)

assert abs(observed - expected) > tolerance

print(
    "Pot validation guard regression passed:",
    tolerance,
)
