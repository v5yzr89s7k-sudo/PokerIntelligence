from src.v017.commitment_normalizer import (
    normalize_commitment_delta,
)


def main():
    # July22-style displayed discrepancy:
    # physical stack delta 3.38 while authoritative price requires 3.37.
    result = normalize_commitment_delta(
        observed_delta_bb=3.38,
        prior_street_commitment_bb=0.0,
        current_price_bb=3.37,
    )

    assert result.observed_delta_bb == 3.38
    assert result.normalized_delta_bb == 3.37
    assert result.snapped_to_call_price is True

    # Exact call remains exact.
    result = normalize_commitment_delta(
        observed_delta_bb=2.0,
        prior_street_commitment_bb=1.0,
        current_price_bb=3.0,
    )

    assert result.normalized_delta_bb == 2.0
    assert result.snapped_to_call_price is True

    # Opening bet must never be modified.
    result = normalize_commitment_delta(
        observed_delta_bb=3.38,
        prior_street_commitment_bb=0.0,
        current_price_bb=0.0,
    )

    assert result.normalized_delta_bb == 3.38
    assert result.snapped_to_call_price is False

    # Materially larger commitment remains materially larger.
    result = normalize_commitment_delta(
        observed_delta_bb=4.0,
        prior_street_commitment_bb=0.0,
        current_price_bb=3.37,
    )

    assert result.normalized_delta_bb == 4.0
    assert result.snapped_to_call_price is False

    # A 0.03 difference is outside the contract.
    result = normalize_commitment_delta(
        observed_delta_bb=3.40,
        prior_street_commitment_bb=0.0,
        current_price_bb=3.37,
    )

    assert result.normalized_delta_bb == 3.40
    assert result.snapped_to_call_price is False

    print(
        "V0.17 COMMITMENT NORMALIZER: PASS"
    )


if __name__ == "__main__":
    main()
