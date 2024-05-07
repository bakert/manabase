from ortools.sat.python import cp_model

# BAKERT linter that sorts imports (isort?)
from .decks import azorius_taxes, mono_w_bodyguards, ooze, ooze_kiki
from .lands import AdarkarWastes, BattlefieldForge, CavesOfKoilos, CelestialColonnade, CreepingTarPit, CrumblingNecropolis, FetidHeath, FireLitThicket, FurycalmSnarl, GlacialFortress, IrrigatedFarmland, Island, MysticGate, Plains, PortTown, PrairieStream, RiverOfTears, StirringWildwood, SunkenRuins, Swamp, VineglimmerSnarl, VividCrag, penny_dreadful_season_32_lands
from .manabase_solver import DEFAULT_WEIGHTS, B, Card, ColorCombination, Deck, G, IslandType, Manabase, ManaCost, Model, PlainsType, R, Turn, U, W, Weights, card, frank, normalized_mana_spend, solve, viable_lands


def test_normalized_mana_spend() -> None:
    assert normalized_mana_spend(Turn(1), 0) == 0
    assert normalized_mana_spend(Turn(1), 1) == 21
    assert normalized_mana_spend(Turn(2), 1) == 0
    assert normalized_mana_spend(Turn(2), 2) == 10
    assert normalized_mana_spend(Turn(2), 3) == 20  # BAKERT it's terrible that this isn't 21
    assert normalized_mana_spend(Turn(3), 4) == 7
    assert normalized_mana_spend(Turn(3), 5) == 14
    assert normalized_mana_spend(Turn(3), 6) == 21
    assert normalized_mana_spend(Turn(4), 6) == 0
    assert normalized_mana_spend(Turn(4), 8) == 10
    assert normalized_mana_spend(Turn(4), 10) == 20  # BAKERT here also
    assert normalized_mana_spend(Turn(5), 12) == 8
    assert normalized_mana_spend(Turn(5), 15) == 20
    assert normalized_mana_spend(Turn(6), 21) == 18  # BAKERT yikes


def test_deck() -> None:
    constraints = frozenset([card("W"), card("RB"), card("WR"), card("5G")])
    assert Deck(constraints, 60).colors == frozenset({W, R, B, G})


def test_viable_lands() -> None:
    lands = frozenset({Plains, Island, Swamp, CelestialColonnade, StirringWildwood, CreepingTarPit})
    assert viable_lands(frozenset({W, U}), lands) == {Plains, Island, CelestialColonnade}


def test_str_repr() -> None:
    c = Card("Ragavan, Nimble Pilferer", ManaCost(R), "Legendary Creature - Monkey Pirate")
    assert str(c) == repr(c) == "Ragavan, Nimble Pilferer"
    assert str(Plains) == repr(Plains) == "Plains"
    assert str(PlainsType) == repr(PlainsType) == "Plains Type"
    assert str(FurycalmSnarl) == repr(FurycalmSnarl) == "Furycalm Snarl"


def test_basic_land_types() -> None:
    assert Island.basic_land_types == {IslandType}
    assert IrrigatedFarmland.basic_land_types == {PlainsType, IslandType}
    assert VineglimmerSnarl.basic_land_types == set()


def test_frank() -> None:
    constraint = card("U")
    assert frank(constraint, 60) == {ColorCombination({U}): 14}
    constraint = card("1G")
    assert frank(constraint, 60) == {ColorCombination({G}): 13}
    constraint = card("WW")
    assert frank(constraint, 60) == {ColorCombination({W}): 13, ColorCombination((W, W)): 21}
    constraint = card("RRB")
    assert frank(constraint, 60) == {
        ColorCombination({R}): 12,  # BAKERT are these redundant when you have an RR? Are they even a bug because they counterfeit filters? We need RR we don't need R at all in a sense
        ColorCombination({B}): 12,
        ColorCombination([R, R]): 18,
        ColorCombination({R, B}): 18,  # BAKERT same q
        ColorCombination([R, R, B]): 23,
    }
    constraint = card("2WW", 6)
    assert frank(constraint, 60) == {ColorCombination({W}): 9, ColorCombination((W, W)): 13}


def test_filter() -> None:
    # # BAKERT an actual test pls
    # model = Model()
    # constraint = card("CCWWUU")
    # print(MysticGate.add_to_model(model, constraint, land_vars))
    pass


def test_tango() -> None:
    constraint = card("U")
    model = Model(Deck(frozenset([constraint]), 60), penny_dreadful_season_32_lands, DEFAULT_WEIGHTS)
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == 0
    constraint = card("2U")
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == model.lands[PrairieStream]


def test_add_to_model() -> None:
    constraint = card("WU")
    model = Model(Deck(frozenset([constraint]), 60), penny_dreadful_season_32_lands, DEFAULT_WEIGHTS)
    contributions = MysticGate.add_to_model(model, constraint)
    assert contributions[ColorCombination([W])] == model.lands[MysticGate]
    assert contributions[ColorCombination([U])] == model.lands[MysticGate]
    multicolor_contribs_s = str(contributions[ColorCombination([W, U])])
    assert "Mystic" in multicolor_contribs_s
    assert "Sunken" not in multicolor_contribs_s
    # BAKERT (W, U) means W || U not W && U, Filter needs to learn that
    # BAKERT can test a lot more here, and should


def test_sort_lands() -> None:
    lands = [GlacialFortress, FireLitThicket, SunkenRuins, AdarkarWastes]
    assert sorted(lands) == [AdarkarWastes, GlacialFortress, SunkenRuins, FireLitThicket]


# BAKERT tests should not use default weights allowing us to change them without breaking the tests
# BAKERT tests should use defined lists of lands like pd s32
def test_solve() -> None:
    solution = solve(mono_w_bodyguards, DEFAULT_WEIGHTS, lands=frozenset({Plains, Island, MysticGate}))
    print(mono_w_bodyguards)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[Plains] == 14
    assert solution.lands.get(Island) is solution.lands.get(MysticGate) is None

    # BAKERT if up normalized_mana_spend even to 2 here I get more than 23 lands which must be a bug?
    weights = Weights(normalized_mana_spend=1, total_lands=-10, pain=-1, total_colored_sources=0)
    solution = solve(azorius_taxes, weights, penny_dreadful_season_32_lands)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.total_lands == 23
    assert solution.lands[PortTown] == 4
    assert solution.lands[Plains] == 10
    # BAKERT when we're more sure about what we want here, assert more. In particular 4 Mystic Gate?

    boros_burn = Deck(frozenset([card("W"), card("R"), card("WR")]), 60)
    solution = solve(boros_burn, weights, penny_dreadful_season_32_lands)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[BattlefieldForge] == 4

    counter_weenie = Deck(frozenset([card("WW"), card("UU")]), 60)
    solution = solve(counter_weenie, weights, penny_dreadful_season_32_lands)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[MysticGate] == 4

    basics_and_tango = frozenset({Plains, Island, PrairieStream})
    light = Deck(frozenset({card("1W"), card("1U")}), 60)
    solution = solve(light, weights, lands=basics_and_tango)
    assert solution
    print(solution)
    assert solution.lands[PrairieStream] == 4
    intense = Deck(frozenset({card("W"), card("U")}), 60)
    solution = solve(intense, weights, lands=basics_and_tango)
    assert solution
    assert not solution.lands.get(PrairieStream)

    necrotic_ooze = Deck(frozenset([card("B", 2), card("UB"), card("WB"), card("2B"), card("3U"), card("2BB")]), 60)
    solution = solve(necrotic_ooze, weights, penny_dreadful_season_32_lands)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert MysticGate not in solution.lands
    assert CrumblingNecropolis not in solution.lands
    # BAKERT should lands understand that it has 0 of everything that isn't present
    assert solution.lands.get(RiverOfTears, 0) == 4

    # BAKERT we can enable this test when colored sources works which will allow the model to pick Vivid Crag over RestlessVents here
    solution = solve(ooze_kiki, weights, penny_dreadful_season_32_lands)
    assert solution  # BAKERT maybe it's better if solve always returns an object, and sometimes it's a solution that says "nope" instead of None?
    # BAKERT this test is flakey
    # assert RestlessVents not in solution.lands if solution.lands.get(VividCrag, 0) < 4 else True

    # BAKERT this solution was found to be optimal for ooze_kiki with WEIGHTS but is not because Vivid Crag is way better than Restless Vents given what the system currently knows:
    # 3 Plains
    # 2 Vivid Crag
    # 4 Fetid Heath
    # 2 Swamp
    # 4 Lavaclaw Reaches
    # 1 Restless Vents
    # 4 Graven Cairns
    # 4 Needle Spires
    #  0.95 (-180)

    # BAKERT we don't cope with no colored constraints, or colorless cards in general?
    # solution = solve(just_a_hammer, weights, penny_dreadful_season_32_lands)
    # assert len(solution.lands) == 23


def test_score() -> None:
    deck = mono_w_bodyguards
    min_plains: Manabase = {Plains: 14}
    excess_plains: Manabase = {Plains: 18}
    good_solution = solve(deck, DEFAULT_WEIGHTS, penny_dreadful_season_32_lands, forced_lands=min_plains)
    bad_solution = solve(deck, DEFAULT_WEIGHTS, penny_dreadful_season_32_lands, forced_lands=excess_plains)
    assert good_solution and bad_solution and good_solution > bad_solution

    # BAKERT define weights here too?
    deck = ooze
    good_lands: Manabase = {
        SunkenRuins: 4,
        FetidHeath: 4,
        Plains: 4,
        Island: 4,
        RiverOfTears: 4,
        VividCrag: 1,
        CavesOfKoilos: 4,
    }
    bad_lands: Manabase = {
        CelestialColonnade: 2,
        IrrigatedFarmland: 1,
        PrairieStream: 4,
        VividCrag: 4,
        MysticGate: 1,
        FetidHeath: 2,
        RiverOfTears: 4,
        Swamp: 6,
    }
    untapped_solution = solve(deck, DEFAULT_WEIGHTS, penny_dreadful_season_32_lands, forced_lands=good_lands)
    assert untapped_solution
    tapped_solution = solve(deck, DEFAULT_WEIGHTS, penny_dreadful_season_32_lands, forced_lands=bad_lands)
    assert tapped_solution
    assert untapped_solution.normalized_score > tapped_solution.normalized_score


def test_mana_spend() -> None:
    deck = ooze
    bad_lands: Manabase = {
        CelestialColonnade: 2,
        IrrigatedFarmland: 1,
        PrairieStream: 4,
        VividCrag: 4,
        MysticGate: 1,
        FetidHeath: 2,
        RiverOfTears: 4,
        Swamp: 6,
    }
    solution = solve(deck, DEFAULT_WEIGHTS, penny_dreadful_season_32_lands, bad_lands)
    assert solution
    assert solution.mana_spend == 6  # BAKERT but maybe it should be "1" or even something normalized over fundamental turn max mana spend?


def test_weights_effects() -> None:
    # BAKERT it might be cool to implement *everything* as a contributor to the objective function and not a constraint to be satisfied
    # because then we could score 24 Wastes as a manabase for azorius taxes and give it 0 instead of None, but that might be mega slow
    azorius_taxes_23: Manabase = {
        Plains: 10,
        CelestialColonnade: 1,
        GlacialFortress: 4,
        IrrigatedFarmland: 2,
        PortTown: 4,
        Island: 2,
    }
    azorius_taxes_25: Manabase = {
        Plains: 12,
        GlacialFortress: 1,
        PortTown: 2,
        MysticGate: 3,
        Island: 7,
    }
    deck = azorius_taxes

    lands_weights = Weights(normalized_mana_spend=1, total_lands=-10, pain=-2, total_colored_sources=0)
    spend_weights = Weights(normalized_mana_spend=20, total_lands=-10, pain=-2, total_colored_sources=0)

    solution23_lands = solve(deck, weights=lands_weights, lands=penny_dreadful_season_32_lands, forced_lands=azorius_taxes_23)
    solution23_spend = solve(deck, weights=spend_weights, lands=penny_dreadful_season_32_lands, forced_lands=azorius_taxes_23)
    assert solution23_lands
    assert solution23_spend
    assert solution23_lands.total_lands == solution23_spend.total_lands == 23

    solution25_lands = solve(deck, weights=lands_weights, lands=penny_dreadful_season_32_lands, forced_lands=azorius_taxes_25)
    solution25_spend = solve(deck, weights=spend_weights, lands=penny_dreadful_season_32_lands, forced_lands=azorius_taxes_25)
    assert solution25_lands
    assert solution25_spend
    assert solution25_lands.total_lands == solution25_spend.total_lands == 25

    assert solution23_lands.mana_spend < solution25_lands.mana_spend
    # When the weight for mana spend is lower it's more important to play less lands …
    assert solution23_lands.normalized_score > solution25_lands.normalized_score
    # … but when the weight for mana spend gets higher we're prepared to play more lands to get an untapped land on t3
    assert solution23_spend.normalized_score < solution25_spend.normalized_score

def test_x() -> None:
    ereboss_intervention = card("XB")
    assert ereboss_intervention.turn == 2
    abandon_hope = card("X1B")
    assert abandon_hope.turn == 3
    decree_of_justice = card("XX2WW")
    assert decree_of_justice.turn == 6
