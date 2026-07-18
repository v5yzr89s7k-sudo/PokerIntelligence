from src.api.api_board_worker import board_is_valid


def assert_valid(board, expected_len):
    ok, reason = board_is_valid(board, expected_len)
    assert ok is True
    assert reason is None


def assert_invalid(board, expected_len, expected_reason):
    ok, reason = board_is_valid(board, expected_len)
    assert ok is False
    assert reason == expected_reason


assert_valid(["Qd", "Jd", "7d"], 3)
assert_valid(["Qd", "Jd", "7d", "5c"], 4)
assert_valid(["Qd", "Jd", "7d", "5c", "As"], 5)

assert_invalid(["4h", "4h", "4h"], 3, "duplicate_cards")
assert_invalid(["Qd", "Jd"], 3, "wrong_length")
assert_invalid(["Qd", "ZZ", "7d"], 3, "invalid_card")
assert_invalid(["qd", "Jd", "7d"], 3, "invalid_card")

print("Board worker validation regression test passed.")
