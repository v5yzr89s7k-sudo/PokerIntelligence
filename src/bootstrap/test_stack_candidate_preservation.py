from src.bootstrap.hero_bootstrap import (
    build_local_players,
    populate_local_stacks,
)


def fake_crop(image, region):
    return image


class FakeImage:
    size = 1


def test_ambiguous_candidates_survive_without_promoting_stack():
    players = build_local_players(
        frozen_participants=["seat_mid_right"],
    )

    result = {
        "raw": [
            {
                "variant": "green",
                "raw": "99.41 BB",
                "stack_bb": 99.41,
            },
            {
                "variant": "plain",
                "raw": "99.41 BB",
                "stack_bb": 99.41,
            },
            {
                "variant": "psm13_t130",
                "raw": "55.41 BB",
                "stack_bb": 55.41,
            },
        ],
        "stack_bb": 99.41,
        "stack_text": "99.41 BB",
        "confidence": 0.50,
        "votes": 1,
        "mode": "segmentation_disagreement",
    }

    populate_local_stacks(
        local_players=players,
        canonical_image=FakeImage(),
        geometry={
            "stack_regions": {
                "seat_mid_right": {
                    "x": 0,
                    "y": 0,
                    "width": 1,
                    "height": 1,
                },
            },
        },
        crop_geometry_region=fake_crop,
        stack_reader=lambda crop: result,
    )

    player = players[0]

    assert player["stack_bb"] is None, player
    assert player["stack_text"] == "", player
    assert player["stack_candidates"] == [
        99.41,
        55.41,
    ], player

    print(
        "PASS bootstrap candidate preservation: "
        "ambiguous 99.41/55.41 evidence survives while "
        "authoritative stack remains unresolved"
    )


def main():
    test_ambiguous_candidates_survive_without_promoting_stack()


if __name__ == "__main__":
    main()
