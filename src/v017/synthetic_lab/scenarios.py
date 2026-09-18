from src.v017.synthetic_lab.scenario_factory import (
    ExpectedAction,
    ExpectedPublication,
    FactoryScenario,
    PhysicalEvidence,
    ScenarioPlayer,
    validate_scenario,
)


# ------------------------------------------------------------
# Scenario 001
#
# Minimal controlled preflop:
#
# UTG folds
# Hero raises to 2 BB
# SB folds
# BB folds
#
# This scenario is deliberately small. Its purpose is to prove the
# generic factory model before we add calls, 3-bets and later streets.
# ------------------------------------------------------------

PREFLOP_OPEN_FOLDS = validate_scenario(
    FactoryScenario(
        name="preflop_open_folds",

        players=(
            ScenarioPlayer(
                seat="utg",
                position="UTG",
                name="UTG",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="hero",
                position="BTN",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),

        action_order=(
            "utg",
            "hero",
            "sb",
            "bb",
        ),

        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",

        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="utg",
            ),

            # Hero 50 -> 48 twice:
            # temporal settlement confirms raise to 2 BB.
            PhysicalEvidence(
                frame=20,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=21,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=48.0,
            ),

            PhysicalEvidence(
                frame=30,
                type="CARD_DISAPPEARANCE",
                seat="sb",
            ),
            PhysicalEvidence(
                frame=40,
                type="CARD_DISAPPEARANCE",
                seat="bb",
            ),
        ),

        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "utg",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "RAISE",
                raise_to_bb=2.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "FOLD",
            ),
        ),

        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="hero",
                required_text=(
                    "UTG folds",
                ),
                forbidden_text=(
                    "BTN (Hero) raises",
                ),
            ),
            ExpectedPublication(
                frame=21,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=(
                    "UTG folds",
                    "BTN (Hero) raises to 2 BB",
                ),
            ),
            ExpectedPublication(
                frame=30,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=(
                    "SB folds",
                ),
            ),
            ExpectedPublication(
                frame=40,
                street="PREFLOP",
                action_count=6,
                next_actor=None,
                required_text=(
                    "BB folds",
                ),
            ),
        ),
    )
)


# ------------------------------------------------------------
# Scenario 002
#
# UTG folds
# Hero BTN raises to 2 BB
# SB folds
# BB calls additional 1 BB
#
# Purpose:
# prove a prior blind commitment plus incremental quantitative
# movement resolves as CALL at the current price.
# ------------------------------------------------------------

PREFLOP_OPEN_CALL = validate_scenario(
    FactoryScenario(
        name="preflop_open_call",
        players=(
            ScenarioPlayer(
                seat="utg",
                position="UTG",
                name="UTG",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="hero",
                position="BTN",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "utg",
            "hero",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="utg",
            ),
            PhysicalEvidence(
                frame=20,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=21,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=30,
                type="CARD_DISAPPEARANCE",
                seat="sb",
            ),
            PhysicalEvidence(
                frame=40,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=49.0,
            ),
            PhysicalEvidence(
                frame=41,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=49.0,
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "utg",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "RAISE",
                raise_to_bb=2.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CALL",
                amount_bb=1.0,
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="hero",
                required_text=("UTG folds",),
                forbidden_text=(
                    "BTN (Hero) raises",
                ),
            ),
            ExpectedPublication(
                frame=21,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=(
                    "BTN (Hero) raises to 2 BB",
                ),
            ),
            ExpectedPublication(
                frame=30,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB folds",),
            ),
            ExpectedPublication(
                frame=41,
                street="PREFLOP",
                action_count=6,
                next_actor=None,
                required_text=(
                    "BB calls 1 BB",
                ),
            ),
        ),
    )
)




# ------------------------------------------------------------
# Scenario 003
#
# UTG folds
# Hero BTN raises to 2 BB
# SB folds
# BB 3-bets to 6 BB
# Hero calls additional 4 BB
#
# Purpose:
# prove aggression resets pending_to_act and reopens Hero's
# obligation after Hero has already acted once.
# ------------------------------------------------------------

PREFLOP_THREE_BET_CALL = validate_scenario(
    FactoryScenario(
        name="preflop_three_bet_call",
        players=(
            ScenarioPlayer(
                seat="utg",
                position="UTG",
                name="UTG",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="hero",
                position="BTN",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "utg",
            "hero",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="utg",
            ),
            PhysicalEvidence(
                frame=20,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=21,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=30,
                type="CARD_DISAPPEARANCE",
                seat="sb",
            ),
            PhysicalEvidence(
                frame=40,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=45.0,
            ),
            PhysicalEvidence(
                frame=41,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=45.0,
            ),
            PhysicalEvidence(
                frame=50,
                type="STACK",
                seat="hero",
                prior=48.0,
                value=44.0,
            ),
            PhysicalEvidence(
                frame=51,
                type="STACK",
                seat="hero",
                prior=48.0,
                value=44.0,
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "utg",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "RAISE",
                raise_to_bb=2.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "RAISE",
                raise_to_bb=6.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "CALL",
                amount_bb=4.0,
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="hero",
                required_text=("UTG folds",),
            ),
            ExpectedPublication(
                frame=21,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=(
                    "BTN (Hero) raises to 2 BB",
                ),
            ),
            ExpectedPublication(
                frame=30,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB folds",),
            ),
            ExpectedPublication(
                frame=41,
                street="PREFLOP",
                action_count=6,
                next_actor="hero",
                required_text=(
                    "BB raises to 6 BB",
                ),
            ),
            ExpectedPublication(
                frame=51,
                street="PREFLOP",
                action_count=7,
                next_actor=None,
                required_text=(
                    "BTN (Hero) calls 4 BB",
                ),
            ),
        ),
    )
)




# ------------------------------------------------------------
# Scenario 005
#
# Short UTG has only 0.4 BB and commits the entire stack while
# facing the 1 BB big-blind price.
# Hero, SB and BB then fold.
#
# Purpose:
# continuously prove that a below-price commitment is admitted
# as CALL only with explicit independent physical all-in evidence.
# ------------------------------------------------------------

PREFLOP_SHORT_ALLIN = validate_scenario(
    FactoryScenario(
        name="preflop_short_allin",
        players=(
            ScenarioPlayer(
                seat="utg",
                position="UTG",
                name="UTG",
                stack_bb=0.4,
            ),
            ScenarioPlayer(
                seat="hero",
                position="BTN",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "utg",
            "hero",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="STACK",
                seat="utg",
                prior=0.4,
                value=0.0,
                all_in_physical=True,
            ),
            PhysicalEvidence(
                frame=11,
                type="STACK",
                seat="utg",
                prior=0.4,
                value=0.0,
                all_in_physical=True,
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=30,
                type="CARD_DISAPPEARANCE",
                seat="sb",
            ),
            PhysicalEvidence(
                frame=40,
                type="CARD_DISAPPEARANCE",
                seat="bb",
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "utg",
                "CALL",
                amount_bb=0.4,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "FOLD",
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=11,
                street="PREFLOP",
                action_count=3,
                next_actor="hero",
                required_text=(
                    "UTG calls 0.4 BB",
                ),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=(
                    "BTN (Hero) folds",
                ),
            ),
            ExpectedPublication(
                frame=30,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB folds",),
            ),
            ExpectedPublication(
                frame=40,
                street="PREFLOP",
                action_count=6,
                next_actor=None,
                required_text=("BB folds",),
            ),
        ),
    )
)




# ------------------------------------------------------------
# Scenario 004
#
# Hero UTG folds
# BTN folds
# SB completes the blind from 0.5 BB to 1 BB
# BB checks
# FLOP appears
#
# BB's zero-chip completion is not injected semantically.
# The physical FLOP boundary proves that the still-pending BB
# completed preflop after already matching the current price.
# HandEngine alone determines that this means CHECK.
# ------------------------------------------------------------

PREFLOP_SB_COMPLETE = validate_scenario(
    FactoryScenario(
        name="preflop_sb_complete",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="UTG",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="btn",
                position="BTN",
                name="BTN",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "btn",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="btn",
            ),
            PhysicalEvidence(
                frame=30,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=31,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=40,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "btn",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CHECK",
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="btn",
                required_text=(
                    "UTG (Hero) folds",
                ),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=(
                    "BTN folds",
                ),
            ),
            ExpectedPublication(
                frame=31,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=(
                    "SB calls 0.5 BB",
                ),
            ),
            ExpectedPublication(
                frame=40,
                street="FLOP",
                action_count=6,
                next_actor="sb",
                required_text=(
                    "BB checks",
                    "As 7d 2c",
                ),
            ),
        ),
        expected_final_street="FLOP",
    )
)




# ------------------------------------------------------------
# L4.4 Scenario 006
#
# Heads-up postflop check/check.
#
# Preflop:
# Hero UTG folds
# BTN folds
# SB completes to 1 BB
# FLOP boundary proves BB check
#
# Flop:
# SB checks
# BB checks
# TURN boundary is the objective downstream proof that both
# zero-chip FLOP actions completed.
# ------------------------------------------------------------

FLOP_CHECK_CHECK = validate_scenario(
    FactoryScenario(
        name="flop_check_check",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="UTG",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="btn",
                position="BTN",
                name="BTN",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "btn",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="btn",
            ),
            PhysicalEvidence(
                frame=30,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=31,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=40,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
            PhysicalEvidence(
                frame=50,
                type="STREET_BOUNDARY",
                street="TURN",
                board=("As", "7d", "2c", "Kh"),
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "btn",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "sb",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "bb",
                "CHECK",
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="btn",
                required_text=("UTG (Hero) folds",),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=("BTN folds",),
            ),
            ExpectedPublication(
                frame=31,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB calls 0.5 BB",),
            ),
            ExpectedPublication(
                frame=40,
                street="FLOP",
                action_count=6,
                next_actor="sb",
                required_text=(
                    "BB checks",
                    "As 7d 2c",
                ),
                forbidden_text=(
                    "SB checks",
                ),
            ),
            ExpectedPublication(
                frame=50,
                street="TURN",
                action_count=8,
                next_actor="sb",
                required_text=(
                    "SB checks",
                    "BB checks",
                    "FLOP: As 7d 2c",
                    "TURN: Kh",
                ),
            ),
        ),
        expected_final_street="TURN",
    )
)


PREFLOP_SCENARIOS = (
    PREFLOP_OPEN_FOLDS,
    PREFLOP_OPEN_CALL,
    PREFLOP_THREE_BET_CALL,
    PREFLOP_SB_COMPLETE,
    PREFLOP_SHORT_ALLIN,
)



# ------------------------------------------------------------
# L4.4 Scenario 007
#
# Heads-up FLOP bet/fold.
#
# Preflop reaches the same authoritative heads-up FLOP as
# Scenario 006.
#
# Flop:
# SB bets 3 BB through settled quantitative stack evidence.
# BB folds through physical card disappearance.
# ------------------------------------------------------------

FLOP_BET_FOLD = validate_scenario(
    FactoryScenario(
        name="flop_bet_fold",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="UTG",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="btn",
                position="BTN",
                name="BTN",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "btn",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="btn",
            ),
            PhysicalEvidence(
                frame=30,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=31,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=40,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
            PhysicalEvidence(
                frame=50,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=46.5,
            ),
            PhysicalEvidence(
                frame=51,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=46.5,
            ),
            PhysicalEvidence(
                frame=60,
                type="CARD_DISAPPEARANCE",
                seat="bb",
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "btn",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "sb",
                "BET",
                amount_bb=3.0,
            ),
            ExpectedAction(
                "FLOP",
                "bb",
                "FOLD",
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="btn",
                required_text=("UTG (Hero) folds",),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=("BTN folds",),
            ),
            ExpectedPublication(
                frame=31,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB calls 0.5 BB",),
            ),
            ExpectedPublication(
                frame=40,
                street="FLOP",
                action_count=6,
                next_actor="sb",
                required_text=("FLOP: As 7d 2c",),
                forbidden_text=("SB bets",),
            ),
            ExpectedPublication(
                frame=51,
                street="FLOP",
                action_count=7,
                next_actor="bb",
                required_text=("SB bets 3 BB",),
                forbidden_text=("BB folds",),
            ),
            ExpectedPublication(
                frame=60,
                street="FLOP",
                action_count=8,
                next_actor=None,
                required_text=(
                    "SB bets 3 BB",
                    "BB folds",
                ),
            ),
        ),
        expected_final_street="FLOP",
    )
)




# ------------------------------------------------------------
# L4.4 Scenario 008
#
# Heads-up FLOP bet/call.
#
# Preflop reaches the same authoritative heads-up FLOP.
#
# Flop:
# SB bets 3 BB through settled quantitative evidence.
# BB calls 3 BB through independent settled quantitative evidence.
# ------------------------------------------------------------

FLOP_BET_CALL = validate_scenario(
    FactoryScenario(
        name="flop_bet_call",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="UTG",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="btn",
                position="BTN",
                name="BTN",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "btn",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="btn",
            ),
            PhysicalEvidence(
                frame=30,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=31,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=40,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
            PhysicalEvidence(
                frame=50,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=46.5,
            ),
            PhysicalEvidence(
                frame=51,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=46.5,
            ),
            PhysicalEvidence(
                frame=60,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=47.0,
            ),
            PhysicalEvidence(
                frame=61,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=47.0,
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "btn",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "sb",
                "BET",
                amount_bb=3.0,
            ),
            ExpectedAction(
                "FLOP",
                "bb",
                "CALL",
                amount_bb=3.0,
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="btn",
                required_text=("UTG (Hero) folds",),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=("BTN folds",),
            ),
            ExpectedPublication(
                frame=31,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB calls 0.5 BB",),
            ),
            ExpectedPublication(
                frame=40,
                street="FLOP",
                action_count=6,
                next_actor="sb",
                required_text=("FLOP: As 7d 2c",),
                forbidden_text=("SB bets",),
            ),
            ExpectedPublication(
                frame=51,
                street="FLOP",
                action_count=7,
                next_actor="bb",
                required_text=("SB bets 3 BB",),
                forbidden_text=("BB calls",),
            ),
            ExpectedPublication(
                frame=61,
                street="FLOP",
                action_count=8,
                next_actor=None,
                required_text=(
                    "SB bets 3 BB",
                    "BB calls 3 BB",
                ),
            ),
        ),
        expected_final_street="FLOP",
    )
)




# ------------------------------------------------------------
# L4.4 Scenario 009
#
# Heads-up FLOP bet/raise/call.
#
# Flop:
# SB bets 3 BB.
# BB raises to 9 BB.
# Aggression must reopen SB's obligation.
# SB calls the additional 6 BB.
# ------------------------------------------------------------

FLOP_RAISE_CALL = validate_scenario(
    FactoryScenario(
        name="flop_raise_call",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="UTG",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="btn",
                position="BTN",
                name="BTN",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "btn",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="btn",
            ),
            PhysicalEvidence(
                frame=30,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=31,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=40,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
            PhysicalEvidence(
                frame=50,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=46.5,
            ),
            PhysicalEvidence(
                frame=51,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=46.5,
            ),
            PhysicalEvidence(
                frame=60,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=41.0,
            ),
            PhysicalEvidence(
                frame=61,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=41.0,
            ),
            PhysicalEvidence(
                frame=70,
                type="STACK",
                seat="sb",
                prior=46.5,
                value=40.5,
            ),
            PhysicalEvidence(
                frame=71,
                type="STACK",
                seat="sb",
                prior=46.5,
                value=40.5,
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "btn",
                "FOLD",
            ),
            ExpectedAction(
                "PREFLOP",
                "sb",
                "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "sb",
                "BET",
                amount_bb=3.0,
            ),
            ExpectedAction(
                "FLOP",
                "bb",
                "RAISE",
                raise_to_bb=9.0,
            ),
            ExpectedAction(
                "FLOP",
                "sb",
                "CALL",
                amount_bb=6.0,
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="btn",
                required_text=("UTG (Hero) folds",),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=("BTN folds",),
            ),
            ExpectedPublication(
                frame=31,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB calls 0.5 BB",),
            ),
            ExpectedPublication(
                frame=40,
                street="FLOP",
                action_count=6,
                next_actor="sb",
                required_text=("FLOP: As 7d 2c",),
                forbidden_text=("SB bets",),
            ),
            ExpectedPublication(
                frame=51,
                street="FLOP",
                action_count=7,
                next_actor="bb",
                required_text=("SB bets 3 BB",),
                forbidden_text=("BB raises",),
            ),
            ExpectedPublication(
                frame=61,
                street="FLOP",
                action_count=8,
                next_actor="sb",
                required_text=(
                    "SB bets 3 BB",
                    "BB raises to 9 BB",
                ),
                forbidden_text=("SB calls 6 BB",),
            ),
            ExpectedPublication(
                frame=71,
                street="FLOP",
                action_count=9,
                next_actor=None,
                required_text=(
                    "BB raises to 9 BB",
                    "SB calls 6 BB",
                ),
            ),
        ),
        expected_final_street="FLOP",
    )
)




# ------------------------------------------------------------
# L4.5 Scenario 010
#
# Vertical PREFLOP -> FLOP -> TURN -> RIVER progression.
#
# FLOP boundary proves BB's preflop zero-chip completion.
# TURN boundary proves both FLOP zero-chip completions.
# TURN uses quantitative BET/CALL evidence.
# On RIVER, BB's later positive commitment objectively proves
# SB completed first at price zero; HandEngine owns CHECK.
# ------------------------------------------------------------

TURN_RIVER_VERTICAL = validate_scenario(
    FactoryScenario(
        name="turn_river_vertical",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="UTG",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="btn",
                position="BTN",
                name="BTN",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="sb",
                position="SB",
                name="SB",
                stack_bb=50.0,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "btn",
            "sb",
            "bb",
        ),
        small_blind_seat="sb",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
            PhysicalEvidence(
                frame=20,
                type="CARD_DISAPPEARANCE",
                seat="btn",
            ),
            PhysicalEvidence(
                frame=30,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=31,
                type="STACK",
                seat="sb",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=40,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
            PhysicalEvidence(
                frame=50,
                type="STREET_BOUNDARY",
                street="TURN",
                board=("As", "7d", "2c", "Kh"),
            ),
            PhysicalEvidence(
                frame=60,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=47.5,
            ),
            PhysicalEvidence(
                frame=61,
                type="STACK",
                seat="sb",
                prior=49.5,
                value=47.5,
            ),
            PhysicalEvidence(
                frame=70,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=71,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=80,
                type="STREET_BOUNDARY",
                street="RIVER",
                board=("As", "7d", "2c", "Kh", "9s"),
            ),
            PhysicalEvidence(
                frame=90,
                type="STACK",
                seat="bb",
                prior=48.0,
                value=44.0,
            ),
            PhysicalEvidence(
                frame=91,
                type="STACK",
                seat="bb",
                prior=48.0,
                value=44.0,
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP", "sb",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP", "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP", "hero", "FOLD",
            ),
            ExpectedAction(
                "PREFLOP", "btn", "FOLD",
            ),
            ExpectedAction(
                "PREFLOP", "sb", "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP", "bb", "CHECK",
            ),
            ExpectedAction(
                "FLOP", "sb", "CHECK",
            ),
            ExpectedAction(
                "FLOP", "bb", "CHECK",
            ),
            ExpectedAction(
                "TURN", "sb", "BET",
                amount_bb=2.0,
            ),
            ExpectedAction(
                "TURN", "bb", "CALL",
                amount_bb=2.0,
            ),
            ExpectedAction(
                "RIVER", "sb", "CHECK",
            ),
            ExpectedAction(
                "RIVER", "bb", "BET",
                amount_bb=4.0,
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=10,
                street="PREFLOP",
                action_count=3,
                next_actor="btn",
                required_text=("UTG (Hero) folds",),
            ),
            ExpectedPublication(
                frame=20,
                street="PREFLOP",
                action_count=4,
                next_actor="sb",
                required_text=("BTN folds",),
            ),
            ExpectedPublication(
                frame=31,
                street="PREFLOP",
                action_count=5,
                next_actor="bb",
                required_text=("SB calls 0.5 BB",),
            ),
            ExpectedPublication(
                frame=40,
                street="FLOP",
                action_count=6,
                next_actor="sb",
                required_text=(
                    "BB checks",
                    "FLOP: As 7d 2c",
                ),
                forbidden_text=("SB checks",),
            ),
            ExpectedPublication(
                frame=50,
                street="TURN",
                action_count=8,
                next_actor="sb",
                required_text=(
                    "SB checks",
                    "BB checks",
                    "TURN: Kh",
                ),
                forbidden_text=("SB bets 2 BB",),
            ),
            ExpectedPublication(
                frame=61,
                street="TURN",
                action_count=9,
                next_actor="bb",
                required_text=("SB bets 2 BB",),
                forbidden_text=("BB calls 2 BB",),
            ),
            ExpectedPublication(
                frame=71,
                street="TURN",
                action_count=10,
                next_actor=None,
                required_text=("BB calls 2 BB",),
            ),
            ExpectedPublication(
                frame=80,
                street="RIVER",
                action_count=10,
                next_actor="sb",
                required_text=("RIVER: 9s",),
                forbidden_text_after=(
                    ("RIVER: 9s", "SB checks"),
                    ("RIVER: 9s", "BB bets 4 BB"),
                ),
            ),
            ExpectedPublication(
                frame=91,
                street="RIVER",
                action_count=12,
                next_actor="sb",
                required_text=(
                    "SB checks",
                    "BB bets 4 BB",
                ),
            ),
        ),
        expected_final_street="RIVER",
    )
)




# ------------------------------------------------------------
# L4.6 Scenario 011
#
# Complete heads-up Hero lifecycle through terminal River fold.
#
# Hero is SB and remains active through the full hand.
#
# FLOP boundary proves BB's preflop zero-chip completion.
# TURN boundary proves both FLOP zero-chip completions.
# TURN uses quantitative Hero BET / BB CALL evidence.
# On RIVER, BB's later quantitative BET proves Hero first
# completed at price zero; HandEngine owns Hero CHECK.
# Hero physical card disappearance then reaches the authoritative
# actor frontier while facing the BB bet; HandEngine owns FOLD.
# The fold leaves one non-folded player, so next_actor becomes None.
# ------------------------------------------------------------

HERO_RIVER_FOLD_TERMINAL = validate_scenario(
    FactoryScenario(
        name="hero_river_fold_terminal",
        players=(
            ScenarioPlayer(
                seat="hero",
                position="SB",
                name="Hero",
                stack_bb=50.0,
                is_hero=True,
            ),
            ScenarioPlayer(
                seat="bb",
                position="BB",
                name="BB",
                stack_bb=50.0,
            ),
        ),
        action_order=(
            "hero",
            "bb",
        ),
        small_blind_seat="hero",
        big_blind_seat="bb",
        hero_seat="hero",
        evidence=(
            PhysicalEvidence(
                frame=10,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=11,
                type="STACK",
                seat="hero",
                prior=50.0,
                value=49.5,
            ),
            PhysicalEvidence(
                frame=20,
                type="STREET_BOUNDARY",
                street="FLOP",
                board=("As", "7d", "2c"),
            ),
            PhysicalEvidence(
                frame=30,
                type="STREET_BOUNDARY",
                street="TURN",
                board=("As", "7d", "2c", "Kh"),
            ),
            PhysicalEvidence(
                frame=40,
                type="STACK",
                seat="hero",
                prior=49.5,
                value=47.5,
            ),
            PhysicalEvidence(
                frame=41,
                type="STACK",
                seat="hero",
                prior=49.5,
                value=47.5,
            ),
            PhysicalEvidence(
                frame=50,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=51,
                type="STACK",
                seat="bb",
                prior=50.0,
                value=48.0,
            ),
            PhysicalEvidence(
                frame=60,
                type="STREET_BOUNDARY",
                street="RIVER",
                board=("As", "7d", "2c", "Kh", "9s"),
            ),
            PhysicalEvidence(
                frame=70,
                type="STACK",
                seat="bb",
                prior=48.0,
                value=44.0,
            ),
            PhysicalEvidence(
                frame=71,
                type="STACK",
                seat="bb",
                prior=48.0,
                value=44.0,
            ),
            PhysicalEvidence(
                frame=80,
                type="CARD_DISAPPEARANCE",
                seat="hero",
            ),
        ),
        expected_actions=(
            ExpectedAction(
                "PREFLOP",
                "hero",
                "POST_SMALL_BLIND",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "POST_BIG_BLIND",
                amount_bb=1.0,
            ),
            ExpectedAction(
                "PREFLOP",
                "hero",
                "CALL",
                amount_bb=0.5,
            ),
            ExpectedAction(
                "PREFLOP",
                "bb",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "hero",
                "CHECK",
            ),
            ExpectedAction(
                "FLOP",
                "bb",
                "CHECK",
            ),
            ExpectedAction(
                "TURN",
                "hero",
                "BET",
                amount_bb=2.0,
            ),
            ExpectedAction(
                "TURN",
                "bb",
                "CALL",
                amount_bb=2.0,
            ),
            ExpectedAction(
                "RIVER",
                "hero",
                "CHECK",
            ),
            ExpectedAction(
                "RIVER",
                "bb",
                "BET",
                amount_bb=4.0,
            ),
            ExpectedAction(
                "RIVER",
                "hero",
                "FOLD",
            ),
        ),
        expected_publications=(
            ExpectedPublication(
                frame=11,
                street="PREFLOP",
                action_count=3,
                next_actor="bb",
                required_text=(
                    "SB (Hero) calls 0.5 BB",
                ),
            ),
            ExpectedPublication(
                frame=20,
                street="FLOP",
                action_count=4,
                next_actor="hero",
                required_text=(
                    "BB checks",
                    "FLOP: As 7d 2c",
                ),
                forbidden_text_after=(
                    ("FLOP: As 7d 2c", "SB (Hero) checks"),
                ),
            ),
            ExpectedPublication(
                frame=30,
                street="TURN",
                action_count=6,
                next_actor="hero",
                required_text=(
                    "SB (Hero) checks",
                    "BB checks",
                    "TURN: Kh",
                ),
                forbidden_text_after=(
                    ("TURN: Kh", "SB (Hero) bets 2 BB"),
                ),
            ),
            ExpectedPublication(
                frame=41,
                street="TURN",
                action_count=7,
                next_actor="bb",
                required_text=(
                    "SB (Hero) bets 2 BB",
                ),
                forbidden_text=(
                    "BB calls 2 BB",
                ),
            ),
            ExpectedPublication(
                frame=51,
                street="TURN",
                action_count=8,
                next_actor=None,
                required_text=(
                    "BB calls 2 BB",
                ),
            ),
            ExpectedPublication(
                frame=60,
                street="RIVER",
                action_count=8,
                next_actor="hero",
                required_text=(
                    "RIVER: 9s",
                ),
                forbidden_text_after=(
                    ("RIVER: 9s", "SB (Hero) checks"),
                    ("RIVER: 9s", "BB bets 4 BB"),
                    ("RIVER: 9s", "SB (Hero) folds"),
                ),
            ),
            ExpectedPublication(
                frame=71,
                street="RIVER",
                action_count=10,
                next_actor="hero",
                required_text=(
                    "SB (Hero) checks",
                    "BB bets 4 BB",
                ),
                forbidden_text_after=(
                    ("RIVER: 9s", "SB (Hero) folds"),
                ),
            ),
            ExpectedPublication(
                frame=80,
                street="RIVER",
                action_count=11,
                next_actor=None,
                required_text=(
                    "BB bets 4 BB",
                    "SB (Hero) folds",
                    "Betting round complete",
                ),
            ),
        ),
        expected_final_street="RIVER",
    )
)


POSTFLOP_SCENARIOS = (
    FLOP_CHECK_CHECK,
    FLOP_BET_FOLD,
    FLOP_BET_CALL,
    FLOP_RAISE_CALL,
    TURN_RIVER_VERTICAL,
    HERO_RIVER_FOLD_TERMINAL,
)

SCENARIOS = (
    PREFLOP_SCENARIOS
    + POSTFLOP_SCENARIOS
)
