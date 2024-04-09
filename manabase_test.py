import pytest
from ortools.sat.python import cp_model

from manabase import AdarkarWastes, B, BattlefieldForge, Card, CelestialColonnade, ColorCombination, CreepingTarPit, CrumblingNecropolis, Deck, FireLitThicket, FurycalmSnarl, G, GlacialFortress, IrrigatedFarmland, Island, IslandType, ManaCost, Model, MysticGate, Plains, PlainsType, PortTown, PrairieStream, R, RememberingModel, RiverOfTears, StirringWildwood, SunkenRuins, Swamp, U, VineglimmerSnarl, W, all_lands, azorius_taxes, card, frank, mono_w_bodyguards, solve, viable_lands
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
    model = Model(Deck(frozenset([constraint]), 60), all_lands)
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == 0
    constraint = card("2U")
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == model.lands[PrairieStream]


def test_add_to_model() -> None:
    constraint = card("WU")
    model = Model(Deck(frozenset([constraint]), 60), all_lands)
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
    solution = solve(Deck(mono_w_bodyguards, 60), frozenset({Plains, Island, MysticGate}))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[Plains] == 14
    assert solution.lands.get(Island) is solution.lands.get(MysticGate) is None

    solution = solve(Deck(azorius_taxes, 60))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    print(solution)
    assert solution.total_lands == 23
    assert solution.lands[PortTown] == 4
    assert solution.lands[Plains] == 10
    # BAKERT when we're more sure about what we want here, assert more. In particular 4 Mystic Gate?

    boros_burn = frozenset([card("W"), card("R"), card("WR")])
    solution = solve(Deck(boros_burn, 60))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[BattlefieldForge] == 4

    counter_weenie = frozenset([card("WW"), card("UU")])
    solution = solve(Deck(counter_weenie, 60))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[MysticGate] == 4

    basics_and_tango = frozenset({Plains, Island, PrairieStream})
    light = frozenset({card("1W"), card("1U")})
    solution = solve(Deck(light, 60), basics_and_tango)
    assert solution
    assert solution.lands[PrairieStream] == 4
    intense = frozenset({card("W"), card("U")})
    solution = solve(Deck(intense, 60), basics_and_tango)
    print(solution)
    assert solution
    assert not solution.lands.get(PrairieStream)

    necrotic_ooze = frozenset([card("B", 2), card("UB"), card("WB"), card("2B"), card("3U"), card("2BB")])
    solution = solve(Deck(necrotic_ooze, 60))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert MysticGate not in solution.lands
    assert CrumblingNecropolis not in solution.lands
    # BAKERT should lands understand that it has 0 of everything that isn't present
    assert solution.lands.get(RiverOfTears, 0) == 4

    # BAKERT we can enable this test when colored sources works which will allow the model to pick Vivid Crag over RestlessVents here
    # solution = solve(Deck(ooze_kiki, 60))
    # print(solution)
    # assert RestlessVents in solution.lands
