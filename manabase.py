from dataclasses import dataclass, field
import copy
import functools
import random
import sys

MAX_DECK_SIZE = 100

@dataclass(eq=True, frozen=True, order=True)
class Color:
    code: str
    name: str

    def __repr__(self):
        return self.code

    def __str__(self):
        return self.__repr__()

W = Color('W', "White")
U = Color('U', "Blue")
B = Color('B', "Black")
R = Color('R', "Red")
G = Color('G', "Green")
C = Color('C', "Colorless")

@dataclass(eq=True, frozen=True, order=True)
class BasicLandType:
    name: str
    produces: Color

    def __repr__(self):
        return f"{self.name} Type"

    def __str__(self):
        return self.__repr__()

PlainsType   = BasicLandType("Plains",   W)
IslandType   = BasicLandType("Island",   U)
SwampType    = BasicLandType("Swamp",    B)
MountainType = BasicLandType("Mountain", R)
ForestType   = BasicLandType("Forest",   G)

all_basic_land_types = {PlainsType, IslandType, SwampType, MountainType, ForestType}

@dataclass(eq=True, frozen=True, order=True)
class ManaCost:
    pips: tuple[Color | int, ...]

    def __init__(self, *args):
        object.__setattr__(self, 'pips', args)

    @property
    def mana_value(self) -> int:
        return sum(1 if isinstance(pip, Color) else pip for pip in self.pips)

    @property
    def colored_pips(self) -> list[Color]:
        return [pip for pip in self.pips if isinstance(pip, Color)]

@dataclass(frozen=True)
class Card:
    name: str
    mana_cost: ManaCost | None
    typeline: str

    @functools.cache
    def untapped(self, turn: int, lands: "LandList") -> bool:
        raise NotImplementedError

    @property
    def max(self) -> int:
        # Some cards break this rule and have specific rules text to say so, including Seven Dwarves as well as unlimited
        return MAX_DECK_SIZE if self.typeline.startswith('Basic Land') else 4

    def __repr__(self) -> str:
        return self.name

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

class CardList(frozenset):
    def __repr__(self):
        return ", ".join(f"{n} {land}" for land, n in sorted(self))

    def __str__(self):
        return self.__repr__()


@dataclass
class Manabase:
    cards: CardList
    score: int

    def __repr__(self) -> str:
        return str(sum(n for _, n in self.cards)) + " (" + str(self.score) + ") " + ", ".join(f"{n} {card}" for card, n in sorted(self.cards))

    def __str__(self):
        return self.__repr__()

@dataclass(eq=True, frozen=True, repr=False)
class Land(Card):
    produces: tuple[Color, ...]
    basic_land_types: frozenset[BasicLandType] = field(default_factory=frozenset, init=False)

    def __post_init__(self):
        object.__setattr__(self, 'basic_land_types', self._calc_basic_land_types())

    def _calc_basic_land_types(self) -> frozenset[BasicLandType]:
        basic_land_types = set()
        for basic_land_type in all_basic_land_types:
            if basic_land_type.name in self.typeline:
                basic_land_types.add(basic_land_type)
        return frozenset(basic_land_types)

    @functools.cache
    def can_produce(self, color: Color) -> bool:
        return color in self.produces

    @functools.cache
    def has_basic_land_types(self, basic_land_types: frozenset[BasicLandType]):
        for basic_land_type in basic_land_types:
            if basic_land_type in self.basic_land_types:
                return True
        return False

class LandList(CardList):
    pass

@dataclass(eq=True, frozen=True, repr=False)
class Basic(Land):
    @functools.cache
    def untapped(self, turn: int, lands: LandList) -> bool:
        return True

@dataclass(eq=True, frozen=True, repr=False)
class Tapland(Land):
    @functools.cache
    def untapped(self, turn: int, lands: LandList) -> bool:
        return False

@dataclass(eq=True, frozen=True, repr=False)
class BasicTypeCaring(Land):
    basic_land_types_needed: frozenset[BasicLandType] = field(default=frozenset(), init=False)

    def __post_init__(self):
        super().__post_init__()
        needed = frozenset({basic_land_type for basic_land_type in all_basic_land_types if basic_land_type.produces in self.produces})
        object.__setattr__(self, 'basic_land_types_needed', needed)

@dataclass(eq=True, frozen=True, repr=False)
class Check(BasicTypeCaring):
    # BAKERT maybe this should be a float, not a bool, for how likely it is to be untapped then multiply by that amount for fractions of a colored mana
    @functools.cache
    def untapped(self, turn: int, lands: LandList) -> bool:
        if turn == 1:
            return False
        needed = num_lands(1, turn)
        # BAKERT includes itself incorrectly
        found = sum(n for land, n in lands if land.has_basic_land_types(self.basic_land_types_needed))
        return found >= needed

@dataclass(eq=True, frozen=True, repr=False)
class Snarl(BasicTypeCaring):
    @functools.cache
    def untapped(self, turn: int, lands: LandList) -> bool:
        # BAKERT shares a lot of code with Check and makes a Snarl a strictly-better Check, which is wrong
        needed = num_lands(1, turn)
        found = sum(n for land, n in lands if land.has_basic_land_types(self.basic_land_types_needed))
        return found >= needed

# BAKERT these cards can produce 2 of a color and that is very relevant for nore than one pip costs and also multicolored, but we don't account for it yet
# BAKERT filters are a little different in that they kind of count for double if you turn them on? Some lands sac to make 2 etc.
@dataclass(eq=True, frozen=True, repr=False)
class Filter(Land):
    @functools.cache
    def untapped(self, turn: int, lands: LandList) -> bool:
        if turn == 1:
            return False
        needed = num_lands(1, turn)
        colors_needed = self.produces
        # BAKERT counting itself here
        found = 0
        for (land, n) in lands:
            for color in colors_needed:
                if color in land.produces:
                    found += n
                    break
        return found > needed

@dataclass(eq=True, frozen=True, repr=False)
class Bicycle(Tapland):
    pass

Wastes   = Basic("Wastes",   None, "Basic Land",   (C,))
Plains   = Basic("Plains",   None, "Basic Land - Plains",   (W,))
Island   = Basic("Island",   None, "Basic Land - Island",   (U,))
Swamp    = Basic("Swamp",    None, "Basic Land - Swamp",    (B,))
Mountain = Basic("Mountain", None, "Basic Land - Mountain", (R,))
Forest   = Basic("Forest",   None, "Basic Land - Forest",   (G,))

# -Wastes
basics = {Plains, Island, Swamp, Mountain, Forest}

ClifftopRetreat   = Check("Clifftop Retreat",   None, "Land", (R, W))
DragonskullSummit = Check("Dragonskull Summit", None, "Land", (B, R))
DrownedCatacomb   = Check("Drowned Catacomb",   None, "Land", (U, B))
GlacialFortress   = Check("Glacial Fortress",   None, "Land", (W, U))
HinterlandHarbor  = Check("Hinterland Harbor",  None, "Land", (G, U))
IsolatedChapel    = Check("Isolated Chapel",    None, "Land", (W, B))
RootboundCrag     = Check("Rootbound Crag",     None, "Land", (R, G))
SulfurFalls       = Check("Sulfur Falls",       None, "Land", (U, R))
SunpetalGrove     = Check("Sunpetal Grove",     None, "Land", (G, W))
WoodlandCemetery  = Check("Woodland Cemetery",  None, "Land", (B, G))

checks = {ClifftopRetreat, DragonskullSummit, DrownedCatacomb, GlacialFortress, HinterlandHarbor, IsolatedChapel, RootboundCrag, SulfurFalls, SunpetalGrove, WoodlandCemetery}

ChokedEstuary     = Snarl("Choked Estuary",     None, "Land", (U, B))
ForebodingRuins   = Snarl("Foreboding Ruins",   None, "Land", (B, R))
FortifiedVillage  = Snarl("Fortified Village",  None, "Land", (G, W))
FrostboilSnarl    = Snarl("Frostboil Snarl",    None, "Land", (U, R))
FurycalmSnarl     = Snarl("Furycalm Snarl",     None, "Land", (R, W))
GameTrail         = Snarl("Game Trail",         None, "Land", (R, G))
NecroblossomSnarl = Snarl("Necroblossom Snarl", None, "Land", (B, G))
PortTown          = Snarl("Port Town",          None, "Land", (W, U))
ShineshadowSnarl  = Snarl("Shineshadow Snarl",  None, "Land", (W, B))
VineglimmerSnarl  = Snarl("Vineglimmer Snarl",  None, "Land", (G, U))

# -FurycalmSnarl, NecroblossomSnarl, ShineshadowSnarl
snarls = {ChokedEstuary, ForebodingRuins, FortifiedVillage, FrostboilSnarl, GameTrail, PortTown, VineglimmerSnarl}

CascadeBluffs  = Filter("Cascade Bluffs",   None, "Land", (U, R))
FetidHeath     = Filter("Fetid Heath",      None, "Land", (W, B))
FireLitThicket = Filter("Fire-Lit Thicket", None, "Land", (R, G))
FloodedGrove   = Filter("Flooded Grove",    None, "Land", (G, U))
GravenCairns   = Filter("Graven Cairns",    None, "Land", (B, R))
MysticGate     = Filter("Mystic Gate",      None, "Land", (W, U))
RuggedPrairie  = Filter("Rugged Prairie",   None, "Land", (R, W))
SunkenRuins    = Filter("Sunken Ruins",     None, "Land", (U, B))
TwilightMire   = Filter("Twilight Mire",    None, "Land", (B, G))
WoodedBastion  = Filter("Wooded Bastion",   None, "Land", (W, G))

# -RuggedPrairie, TwilightMire
filters = {CascadeBluffs, FetidHeath, FireLitThicket, FloodedGrove, GravenCairns, MysticGate, SunkenRuins, WoodedBastion}

CanyonSlough = Bicycle("Canyon Slough", None, "Land - Swamp Mountain", (B, R))
FetidPools = Bicycle("Fetid Pools", None, "Land - Island Swamp", (U, B))
IrrigatedFarmland = Bicycle("Irrigated Farmland", None, "Land - Plains Island", (W, U))
ScatteredGroves = Bicycle("Scattered Groves", None, "Land - Forest Plains", (G, W))
ShelteredThicket = Bicycle("Sheltered Thicket", None, "Land - Mountain Forest", (R, G))

bicycles = {CanyonSlough, FetidPools, IrrigatedFarmland, ScatteredGroves, ShelteredThicket}

CelestialColonnade = Tapland("Celestial Colonnade", None, "Land", (W, U))
CreepingTarPit     = Tapland("Creeping Tar Pit",    None, "Land", (U, B))
HissingQuagmire    = Tapland("Hissing Quagmire",    None, "Land", (B, G))
LavaclawReaches    = Tapland("Lavaclaw Reaches",    None, "Land", (B, R))
LumberingFalls     = Tapland("Lumbering Falls",     None, "Land", (G, U))
NeedleSpires       = Tapland("Needle Spires",       None, "Land", (R, W))
RagingRavine       = Tapland("Raging Ravine",       None, "Land", (R, G))
ShamblingVent      = Tapland("Shambling Vent",      None, "Land", (W, B))
StirringWildwood   = Tapland("Stirring Wildwood",   None, "Land", (G, W))
WanderingFumarole  = Tapland("Wandering Fumarole",  None, "Land", (U, R))

# BAKERT
# Tapland("Restless Anchorage",  None, "Land", (X, Y)),
# Tapland("Restless Bivouac",    None, "Land", (X, Y)),
# Tapland("Restless Cottage",    None, "Land", (X, Y)),
# Tapland("Restless Fortress",   None, "Land", (X, Y)),
# Tapland("Restless Prairie",    None, "Land", (X, Y)),
# Tapland("Restless Reef",       None, "Land", (X, Y)),
# Tapland("Restless Ridgeline",  None, "Land", (X, Y)),
# Tapland("Restless Spire",      None, "Land", (X, Y)),
# Tapland("Restless Vents",      None, "Land", (X, Y)),
# Tapland("Restless Vinestalk",  None, "Land", (X, Y)),

# -CreepingTarPit
creature_lands = {CelestialColonnade, HissingQuagmire, LavaclawReaches, LumberingFalls, NeedleSpires, RagingRavine, ShamblingVent, StirringWildwood, WanderingFumarole}

GrandColiseum = Tapland("Grand Coliseum", None, "Land", (W, U, B, R, G))
VividCrag = Tapland("Vivid Crag", None, "Land", (W, U, B, R, G))

# BAKERT PrarieStream and the GW one

# no creaturelands for now for speed
all_lands: set[Land] = basics.union(checks).union(snarls).union(bicycles).union(filters).union({GrandColiseum, VividCrag})

@dataclass(eq=True, frozen=True, order=True)
class Constraint:
    required: ManaCost
    turn: int = -1

    def __post_init__(self):
        if self.turn == -1:
            object.__setattr__(self, 'turn', self.required.mana_value)

def generate_manabase(constraints: list[Constraint], candidate_lands: set[Land], min_size: int, max_size: int, starting: dict[Land, int]) -> Manabase:
    possible_lands, lands_counter, finished, lands, manabase_score = copy.deepcopy(candidate_lands), copy.copy(starting), False, LandList(), 0
    while not finished:
        if not possible_lands:
            raise NoPossibleLands
        pick = random.choice(tuple(possible_lands))
        lands_counter[pick] = lands_counter.get(pick, 0) + 1
        if lands_counter[pick] >= pick.max:
            possible_lands.discard(pick)
        lands = LandList(lands_counter.items())
        n = sum(n for land, n in lands)
        if n < min_size:
            continue
        manabase_score = score(constraints, lands)
        finished = manabase_score > 0 or n > max_size
    return Manabase(lands, score=manabase_score)

def solve(constraints: list[Constraint], hint: dict[Land, int] | None = None) -> None:
    starting = hint or {}
    # BAKERT simplify the constraints by removing those that are shadowed by others first
    colors = all_colors(constraints)
    possible_lands = viable_lands(colors, all_lands)
    best, seen = None, set()
    min_lands = max(num_lands_required(constraint) for constraint in constraints)
    while True:
        manabase = generate_manabase(constraints, possible_lands, min_lands, MAX_DECK_SIZE, starting)
        if best is None or manabase.score >= best.score and str(manabase) not in seen:
            best = manabase
            seen.add(str(manabase))
            print(best)

def all_colors(constraints: list[Constraint]) -> set[Color]:
    colors = set()
    for constraint in constraints:
        for pip in constraint.required.colored_pips:
            colors.add(pip)
    return colors

def viable_lands(colors: set[Color], lands: set[Land]) -> set[Land]:
    possible_lands = set()
    for land in lands:
        # BAKERT some simplifying pd-specific assumptions here about what lands we might be interested in
        if len(colors.intersection(land.produces)) >= 2 or (colors.intersection(land.produces) and isinstance(land, Basic)):
            possible_lands.add(land)
    return possible_lands

def score(constraints: list[Constraint], lands: LandList) -> int:
    for constraint in constraints:
        if not satisfied(constraint, lands):
            # print(f"Fails on {constraint}")
            return 0
    return MAX_DECK_SIZE - sum(n for land, n in lands) # BAKERT add a smaller value to represent "has even more W sources than you need" or "has some creaturelands" etc.

@functools.cache
def satisfied(constraint: Constraint, lands: LandList) -> bool:
    required = frank(constraint)
    for color, n in required.items():
        sources = sum(num for land, num in lands if land.can_produce(color))
        if sources < n:
            return False
        # BAKERT we need to subtract self from lands, so you can't count yourself as enabling your untappedness
        untapped = num_untapped(constraint.turn, lands)
        need = need_untapped(constraint.turn)
        if untapped < need:
            return False
    return True

@functools.cache
def num_lands_required(constraint: Constraint) -> int:
    return num_lands(constraint.required.mana_value, constraint.turn)

@functools.cache
def need_untapped(turn: int) -> int:
    try:
        return frank(Constraint(ManaCost(C), turn))[C]
    except UnsatisfiableConstraint:
        # We don't know how many untapped lands you need beyond turn 6 so supply an overestimate
        return frank(Constraint(ManaCost(C), 6))[C]

@functools.cache
def num_untapped(turn: int, lands: LandList) -> int:
    found = 0
    for land, n in lands:
        if land.untapped(turn, lands):
            found += n
    return found

class UnsatisfiableConstraint(Exception):
    pass

class NoPossibleLands(Exception):
    pass

# BAKERT this is not the latest numbers? There's one from 2024?
# https://www.channelfireball.com/article/how-many-sources-do-you-need-to-consistently-cast-your-spells-a-2022-update/dc23a7d2-0a16-4c0b-ad36-586fcca03ad8/
@functools.cache
def frank(constraint: Constraint, deck_size: int = 60) -> dict[Color, int]:
    table = {
        (1, 1): {60: 14, 80: 19, 99: 19, 40:  9}, # C     Monastery Swiftspear
        (1, 2): {60: 13, 80: 18, 99: 19, 40:  9}, # 1C    Ledger Shredder
        (2, 2): {60: 21, 80: 28, 99: 30, 40: 14}, # CC    Lord of Atlantis
        (1, 3): {60: 12, 80: 16, 99: 18, 40:  8}, # 2C    Reckless Stormseeker
        (2, 3): {60: 18, 80: 25, 99: 28, 40: 12}, # 1CC   Narset, Parter of Veils
        (3, 3): {60: 23, 80: 32, 99: 36, 40: 16}, # CCC   Goblin Chainwhirler
        (1, 4): {60: 10, 80: 15, 99: 16, 40:  7}, # 3C    Collected Company
        (2, 4): {60: 16, 80: 23, 99: 26, 40: 11}, # 2CC   Wrath of God
        (3, 4): {60: 21, 80: 29, 99: 33, 40: 14}, # 1CCC  Cryptic Command
        (4, 4): {60: 24, 80: 34, 99: 39, 40: 17}, # CCCC  Dawn Elemental
        (1, 5): {60:  9, 80: 14, 99: 15, 40:  6}, # 4C    Doubling Season
        (2, 5): {60: 15, 80: 20, 99: 23, 40: 10}, # 3CC   Baneslayer Angel
        (3, 5): {60: 19, 80: 26, 99: 30, 40: 13}, # 2CCC  Garruk, Primal Hunter
        (4, 5): {60: 22, 80: 31, 99: 36, 40: 15}, # 1CCCC Unnatural Growth
        (1, 6): {60:  9, 80: 12, 99: 14, 40:  6}, # 5C    Drowner of Hope
        (2, 6): {60: 13, 80: 19, 99: 22, 40:  9}, # 4CC   Primeval Titan
        (3, 6): {60: 16, 80: 22, 99: 26, 40: 10}, # 3CCC  Massacre Wurm
        (2, 7): {60: 12, 80: 17, 99: 20, 40:  8}, # 5CC   Hullbreaker Horror
        (3, 7): {60: 16, 80: 22, 99: 26, 40: 10}, # 4CCC  Nyxbloom Ancient
    }
    colored_pips: dict[Color, int] = {}
    results = {}
    for color in constraint.required.colored_pips:
        colored_pips[color] = colored_pips.get(color, 0) + 1
    for color, n in colored_pips.items():
        key = (n, constraint.turn)
        if not table.get(key, {}).get(deck_size):
            raise UnsatisfiableConstraint(key)
        results[color] = table[key][deck_size]
    return results

@functools.cache
def num_lands(mana_value: int, turn: int) -> int:
    try:
        return frank(Constraint(turn=turn, required=ManaCost(*[W] * mana_value)))[W]
    except UnsatisfiableConstraint:
        # We are at mana value 5 or beyond, return an underestimate, but better than nothing
        return frank(Constraint(turn=4, required=ManaCost(*[W] * 4)))[W]

# BAKERT Include Constraint(ManaCost(R), 2) and others once eliding redundant requirements is implemented
jeskai_twin = [Constraint(ManaCost(1, U)), Constraint(ManaCost(3, W)), Constraint(ManaCost(2, R, R, R))]
# BAKERT this should know about three drops, so it knows to play 24 land.
azorius_taxes = [Constraint(ManaCost(W), 1), Constraint(ManaCost(W, W), 2), Constraint(ManaCost(U, W), 2), Constraint(ManaCost(1, U), 2)]
azorius_taxes_postboard = azorius_taxes + [Constraint(ManaCost(2, W, W), 4)]

def test_num_untapped():
    lands = LandList({(basic, 1) for basic in basics})
    for turn in range(1, 8):
        assert num_untapped(turn, lands) == len(lands)
    lands = LandList({(land, 1) for land in creature_lands})
    for turn in range(1, 8):
        assert num_untapped(turn, lands) == 0 # BAKERT this fails to account for trying to cast a 2 drop on turn 3 off all taplands
    lands = LandList({(Plains, 20), (Island, 13)})
    for turn in range(1, 8):
        assert num_untapped(turn, lands) == 33 # BAKERT this fails to account for trying to cast a 2 drop on turn 3 off all taplands

def test_viable_lands():
    lands = {Plains, Island, Swamp, CelestialColonnade, StirringWildwood, CreepingTarPit}
    assert viable_lands({W, U}, lands) == {Plains, Island, CelestialColonnade}

def test_str_repr():
    card = Card("Ragavan, Nimble Pilferer", ManaCost(R), "Legendary Creature - Monkey Pirate")
    assert str(card) == repr(card) == "Ragavan, Nimble Pilferer"
    assert str(Plains) == repr(Plains) == "Plains"
    assert str(PlainsType) == repr(PlainsType) == "Plains Type"
    assert str(FurycalmSnarl) == repr(FurycalmSnarl) == "Furycalm Snarl"

def test_basic_land_types():
    assert Island.basic_land_types == {IslandType}
    assert IrrigatedFarmland.basic_land_types == {PlainsType, IslandType}
    assert VineglimmerSnarl.basic_land_types == set()

def test_untapped():
    lands = LandList({(Plains, 20), (MysticGate, 4), (PortTown, 4), (GlacialFortress, 4)})
    assert PortTown.untapped(1, lands)
    assert PortTown.untapped(2, lands)
    assert Plains.untapped(1, lands)
    assert Plains.untapped(2, lands)
    assert not MysticGate.untapped(1, lands)
    assert MysticGate.untapped(2, lands)
    assert not GlacialFortress.untapped(1, lands)
    assert GlacialFortress.untapped(2, lands)
    lands = LandList({(Mountain, 20), (MysticGate, 4)})
    assert not MysticGate.untapped(1, lands)
    assert not MysticGate.untapped(10, lands)


def test_azorius_taxes_maindeck():
    lands = LandList({
        (Plains, 10),
        (IrrigatedFarmland, 2),
        (Island, 2),
        (MysticGate, 4),
        (GlacialFortress, 1),
        (PortTown, 4),
    })
    assert score(azorius_taxes, lands) > 0
    lands = LandList({
        (GrandColiseum, 4),
        (IrrigatedFarmland, 4),
        (Island, 2),
        (MysticGate, 1),
        (Plains, 8),
        (PortTown, 4),
    })
    assert score(azorius_taxes, lands) > 0

def test_jeskai_twin():
    lands = LandList({
        (VividCrag, 4),
        (GrandColiseum, 4),
        (Mountain, 9),
        (Island, 3),
        (Plains, 2),
        (SulfurFalls, 2),
    })
    assert score(jeskai_twin, lands) > 0

def test():
    test_num_untapped()
    test_viable_lands()
    test_str_repr()
    test_basic_land_types()
    test_untapped()
    test_azorius_taxes_maindeck()
    test_jeskai_twin()

if len(sys.argv) >= 2 and (sys.argv[1] == '--test' or sys.argv[1] == '-t'):
    test()
else:
    # solve(jeskai_twin, Cards({GrandColiseum: 4, VividCrag: 4}))
    import cProfile
    cProfile.run("solve(jeskai_twin)")

# BAKERT
# Phyrexian mana
# Hybrid mana
# Snow mana and snow lands and snow-covered basics
# Yorion
# Commander
# Limited
