import pytest
from ortools.sat.python import cp_model

from manabase import WEIGHTS, AdarkarWastes, B, BattlefieldForge, Card, CavesOfKoilos, CelestialColonnade, ColorCombination, CreepingTarPit, CrumblingNecropolis, Deck, FetidHeath, FireLitThicket, FurycalmSnarl, G, GlacialFortress, IrrigatedFarmland, Island, IslandType, Land, ManaCost, Model, MysticGate, Plains, PlainsType, PortTown, PrairieStream, R, RememberingModel, RestlessVents, RiverOfTears, StirringWildwood, SunkenRuins, Swamp, U, VineglimmerSnarl, VividCrag, W, Weights, all_lands, azorius_taxes, card, frank, mono_w_bodyguards, ooze, ooze_kiki, solve, viable_lands
from remembering_model import KeyCollision


def test_deck() -> None:
    constraints = frozenset([card("W"), card("RB"), card("WR"), card("5G")])
    assert Deck(constraints, 60).colors == frozenset({W, R, B, G})


def test_remembering_model_collision() -> None:
    model = RememberingModel()
    model.new_int_var(0, 1, ("test",))
    model.new_int_var(0, 1, ("test", "other"))
    with pytest.raises(KeyCollision):
        model.new_int_var(0, 2, ("test",))


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
    assert frank(constraint) == {ColorCombination({U}): 14}
    constraint = card("1G")
    assert frank(constraint) == {ColorCombination({G}): 13}
    constraint = card("WW")
    assert frank(constraint) == {ColorCombination({W}): 13, ColorCombination((W, W)): 21}
    constraint = card("RRB")
    assert frank(constraint) == {
        ColorCombination({R}): 12,  # BAKERT are these redundant when you have an RR? Are they even a bug because they counterfeit filters? We need RR we don't need R at all in a sense
        ColorCombination({B}): 12,
        ColorCombination([R, R]): 18,
        ColorCombination({R, B}): 18,  # BAKERT same q
        ColorCombination([R, R, B]): 23,
    }
    constraint = card("2WW", 6)
    assert frank(constraint) == {ColorCombination({W}): 9, ColorCombination((W, W)): 13}


def test_filter() -> None:
    # # BAKERT an actual test pls
    # model = Model()
    # constraint = card("CCWWUU")
    # land_vars = {land: model.new_int_var(0, land.max, land.name) for land in all_lands}
    # print(MysticGate.add_to_model(model, constraint, land_vars))
    pass


def test_tango() -> None:
    constraint = card("U")
    model = Model(Deck(frozenset([constraint]), 60), all_lands, WEIGHTS)
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == 0
    constraint = card("2U")
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == model.lands[PrairieStream]


def test_add_to_model() -> None:
    constraint = card("WU")
    model = Model(Deck(frozenset([constraint]), 60), all_lands, WEIGHTS)
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


def test_solve() -> None:
    solution = solve(Deck(mono_w_bodyguards, 60), WEIGHTS, lands=frozenset({Plains, Island, MysticGate}))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[Plains] == 14
    assert solution.lands.get(Island) is solution.lands.get(MysticGate) is None

    solution = solve(Deck(azorius_taxes, 60), WEIGHTS)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.total_lands == 23
    assert solution.lands[PortTown] == 4
    assert solution.lands[Plains] == 10
    # BAKERT when we're more sure about what we want here, assert more. In particular 4 Mystic Gate?

    boros_burn = frozenset([card("W"), card("R"), card("WR")])
    solution = solve(Deck(boros_burn, 60), WEIGHTS)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[BattlefieldForge] == 4

    counter_weenie = frozenset([card("WW"), card("UU")])
    solution = solve(Deck(counter_weenie, 60), WEIGHTS)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[MysticGate] == 4

    basics_and_tango = frozenset({Plains, Island, PrairieStream})
    light = frozenset({card("1W"), card("1U")})
    solution = solve(Deck(light, 60), WEIGHTS, lands=basics_and_tango)
    assert solution
    assert solution.lands[PrairieStream] == 4
    intense = frozenset({card("W"), card("U")})
    solution = solve(Deck(intense, 60), WEIGHTS, lands=basics_and_tango)
    assert solution
    assert not solution.lands.get(PrairieStream)

    necrotic_ooze = frozenset([card("B", 2), card("UB"), card("WB"), card("2B"), card("3U"), card("2BB")])
    solution = solve(Deck(necrotic_ooze, 60), WEIGHTS)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert MysticGate not in solution.lands
    assert CrumblingNecropolis not in solution.lands
    # BAKERT should lands understand that it has 0 of everything that isn't present
    assert solution.lands.get(RiverOfTears, 0) == 4

    # BAKERT we can enable this test when colored sources works which will allow the model to pick Vivid Crag over RestlessVents here
    solution = solve(Deck(ooze_kiki, 60), WEIGHTS)
    assert solution  # BAKERT maybe it's better if solve always returns an object and sometimes it's a solution that says "nope" instead of None?
    assert RestlessVents not in solution.lands


def test_score() -> None:
    deck = Deck(mono_w_bodyguards, 60)
    min_plains: dict[Land, int] = {Plains: 14}
    excess_plains: dict[Land, int] = {Plains: 18}
    good_solution = solve(deck, WEIGHTS, forced_lands=min_plains)
    bad_solution = solve(deck, WEIGHTS, forced_lands=excess_plains)
    assert good_solution and bad_solution and good_solution > bad_solution

    # BAKERT more these definitions into the tests and don't share them with "scratch" so the tests are stable
    # BAKERT define weights here too?
    deck = Deck(ooze, 60)
    good_lands = {
        SunkenRuins: 4,
        FetidHeath: 4,
        Plains: 4,
        Island: 4,
        RiverOfTears: 4,
        VividCrag: 1,
        CavesOfKoilos: 4,
    }
    bad_lands = {
        CelestialColonnade: 2,
        IrrigatedFarmland: 1,
        PrairieStream: 4,
        VividCrag: 4,
        MysticGate: 1,
        FetidHeath: 2,
        RiverOfTears: 4,
        Swamp: 6,
    }
    untapped_solution = solve(deck, WEIGHTS, forced_lands=good_lands)
    assert untapped_solution
    tapped_solution = solve(deck, WEIGHTS, forced_lands=bad_lands)
    assert tapped_solution
    assert untapped_solution.normalized_score > tapped_solution.normalized_score


def test_mana_spend() -> None:
    deck = Deck(ooze, 60)
    bad_lands = {
        CelestialColonnade: 2,
        IrrigatedFarmland: 1,
        PrairieStream: 4,
        VividCrag: 4,
        MysticGate: 1,
        FetidHeath: 2,
        RiverOfTears: 4,
        Swamp: 6,
    }
    solution = solve(deck, WEIGHTS, all_lands, bad_lands)
    assert solution
    assert solution.mana_spend == 6  # BAKERT but maybe it should be "1" or even something normalized over fundamental turn max mana spend?


def test_weights_effects() -> None:
    # BAKERT it might be cool to implement *everything* as a contributor to the objective function and not a constraint to be satisfied
    # because then we could score 24 Wastes as a manabase for azorious taxes and give it 0 instead of None, but that might be mega slow
    azorius_taxes_23 = {
        Plains: 10,
        CelestialColonnade: 1,
        GlacialFortress: 4,
        IrrigatedFarmland: 2,
        PortTown: 4,
        Island: 2,
    }
    azorius_taxes_25 = {
        Plains: 12,
        GlacialFortress: 1,
        PortTown: 2,
        MysticGate: 3,
        Island: 7,
    }
    # BAKERT all our helper vars should probably be Decks not frozenset(Constraint)
    deck = Deck(azorius_taxes, 60)

    lands_weights = Weights(mana_spend=6, total_lands=-10, pain=-2, total_colored_sources=0)
    spend_weights = Weights(mana_spend=20, total_lands=-10, pain=-2, total_colored_sources=0)

    solution23_lands = solve(deck, weights=lands_weights, forced_lands=azorius_taxes_23)
    solution23_spend = solve(deck, weights=spend_weights, forced_lands=azorius_taxes_23)
    assert solution23_lands
    assert solution23_spend
    assert solution23_lands.total_lands == solution23_spend.total_lands == 23

    solution25_lands = solve(deck, weights=lands_weights, forced_lands=azorius_taxes_25)
    solution25_spend = solve(deck, weights=spend_weights, forced_lands=azorius_taxes_25)
    assert solution25_lands
    assert solution25_spend
    assert solution25_lands.total_lands == solution25_spend.total_lands == 25

    assert solution23_lands.mana_spend < solution25_lands.mana_spend
    # When the weight for mana spend is lower it's more important to play less lands …
    assert solution23_lands.normalized_score > solution25_lands.normalized_score
    # … but when the weight for mana spend gets higher we're prepared to play more lands to get an untapped land on t3
    assert solution23_spend.normalized_score < solution25_spend.normalized_score
