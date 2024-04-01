from dataclasses import dataclass, field
import sys
from typing import Callable, Any

from ortools.sat.python import cp_model

MAX_DECK_SIZE = 100


@dataclass
class Model:
    debug: bool = False
    vars: list[cp_model.IntVar | cp_model.BoolVarT] = field(default_factory=list)
    model: cp_model.CpModel = field(init=False)

    def __post_init__(self) -> None:
        self.model = cp_model.CpModel()

    def add(self, constraint: cp_model.BoundedLinearExpression) -> cp_model.Constraint:
        if self.debug:
            print("[MODEL]", constraint, file=sys.stderr)
        return self.model.Add(constraint)

    def __getattr__(self, name: str) -> Callable:
        def wrapper(*args: list[Any], **kwargs: dict[str, Any]) -> cp_model.IntVar | cp_model.BoolVarT:
            if self.debug:
                print("[MODEL]", name, args, kwargs)
            v = getattr(self.model, name)(*args, **kwargs)
            if name in ["NewBoolVar", "NewIntVar"]:
                self.vars.append(v)
            return v

        return wrapper


@dataclass(eq=True, frozen=True, order=True)
class Color:
    code: str
    name: str

    def __repr__(self) -> str:
        return self.code

    def __str__(self) -> str:
        return self.__repr__()


W = Color("W", "White")
U = Color("U", "Blue")
B = Color("B", "Black")
R = Color("R", "Red")
G = Color("G", "Green")
C = Color("C", "Colorless")

all_colors = {W, U, B, R, G, C}

@dataclass(eq=True, frozen=True, order=True)
class BasicLandType:
    name: str
    produces: Color

    def __repr__(self) -> str:
        return f"{self.name} Type"

    def __str__(self) -> str:
        return self.__repr__()


PlainsType = BasicLandType("Plains", W)
IslandType = BasicLandType("Island", U)
SwampType = BasicLandType("Swamp", B)
MountainType = BasicLandType("Mountain", R)
ForestType = BasicLandType("Forest", G)

all_basic_land_types = {PlainsType, IslandType, SwampType, MountainType, ForestType}


@dataclass(eq=True, frozen=True, order=True)
class ManaCost:
    pips: tuple[Color | int, ...]

    def __init__(self, *args: Color | int) -> None:
        object.__setattr__(self, "pips", args)

    @property
    def mana_value(self) -> int:
        return sum(1 if isinstance(pip, Color) else pip for pip in self.pips)

    @property
    def colored_pips(self) -> list[Color]:
        return [pip for pip in self.pips if isinstance(pip, Color)]

    def __repr__(self):
        return "".join(str(pip) for pip in self.pips)


@dataclass(frozen=True)
class Card:
    name: str
    mana_cost: ManaCost | None
    typeline: str

    @property
    def max(self) -> int:
        # Some cards break this rule and have specific rules text to say so, including Seven Dwarves as well as unlimited
        return MAX_DECK_SIZE if self.typeline.startswith("Basic Land") else 4

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return False
        return self.name == other.name

    def __lt__(self, other: "Card") -> bool:
        return self.name < other.name


@dataclass(eq=True, frozen=True, repr=False)
class Land(Card):
    produces: tuple[Color, ...]
    painful: bool = False
    basic_land_types: frozenset[BasicLandType] = field(default_factory=frozenset, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "basic_land_types", self._calc_basic_land_types())

    def _calc_basic_land_types(self) -> frozenset[BasicLandType]:
        basic_land_types = set()
        for basic_land_type in all_basic_land_types:
            if basic_land_type.name in self.typeline:
                basic_land_types.add(basic_land_type)
        return frozenset(basic_land_types)

    def can_produce(self, color: Color) -> bool:
        return color in self.produces

    def has_basic_land_types(self, basic_land_types: frozenset[BasicLandType]) -> bool:
        for basic_land_type in basic_land_types:
            if basic_land_type in self.basic_land_types:
                return True
        return False

    def untapped_rules(self, model: Model, turn: int, land_vars: dict["Land", cp_model.IntVar]) -> cp_model.IntVar | int:
        raise NotImplementedError


@dataclass(eq=True, frozen=True, repr=False)
class Basic(Land):
    def untapped_rules(self, model: Model, turn: int, land_vars: dict[Land, cp_model.IntVar]) -> cp_model.IntVar | int:
        return land_vars[self]


@dataclass(eq=True, frozen=True, repr=False)
class Tapland(Land):
    def untapped_rules(self, model: Model, turn: int, land_vars: dict["Land", cp_model.IntVar]) -> cp_model.IntVar | int:
        return 0


@dataclass(eq=True, frozen=True, repr=False)
class BasicTypeCaring(Land):
    basic_land_types_needed: frozenset[BasicLandType] = field(default=frozenset(), init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        needed = frozenset({basic_land_type for basic_land_type in all_basic_land_types if basic_land_type.produces in self.produces})
        object.__setattr__(self, "basic_land_types_needed", needed)

    # BAKERT these are specifically Snarl rules which makes it a bit odd to put them on BasicTypeCaring
    # BAKERT a Snarl on a turn after t1 cannot count the lands that you have played towards the total, it has to be in hand
    def untapped_rules(self, model: Model, turn: int, land_vars: dict[Land, cp_model.IntVar]) -> cp_model.IntVar | int:
        enabling_lands = {var for land, var in land_vars.items() if land.has_basic_land_types(self.basic_land_types_needed)}
        untapped_var = model.NewBoolVar(f"{self.name}_Untapped_On_T{turn}")
        needed = need_untapped(turn)
        required_sum = sum(enabling_lands)
        model.add(required_sum >= needed).OnlyEnforceIf(untapped_var)
        model.add(required_sum < needed).OnlyEnforceIf(untapped_var.Not())
        makes_mana_var = model.NewIntVar(0, 4, f"{self.name}_Makes_Mana_On_T{turn}")
        model.add(makes_mana_var == land_vars[self]).OnlyEnforceIf(untapped_var)
        model.add(makes_mana_var == 0).OnlyEnforceIf(untapped_var.Not())
        return makes_mana_var


@dataclass(eq=True, frozen=True, repr=False)
class Check(BasicTypeCaring):
    def untapped_rules(self, model: Model, turn: int, land_vars: dict[Land, cp_model.IntVar]) -> cp_model.IntVar | int:
        if turn <= 1:
            return 0
        return super().untapped_rules(model, turn, land_vars)


@dataclass(eq=True, frozen=True, repr=False)
class Snarl(BasicTypeCaring):
    pass


# BAKERT these cards can produce 2 of a color and that is very relevant for nore than one pip costs and also multicolored, but we don't account for it yet
@dataclass(eq=True, frozen=True, repr=False)
class Filter(Land):
    def untapped_rules(self, model: Model, turn: int, land_vars: dict[Land, cp_model.IntVar]) -> cp_model.IntVar | int:
        if turn <= 1:
            return 0
        enabling_lands = {var for land, var in land_vars.items() if not isinstance(land, Filter) and any(produce in self.produces for produce in land.produces)}
        usable_for_colored_mana_var = model.NewBoolVar(f"{self.name}_Usable_For_Colored_Mana_On_T{turn}")
        needed = need_untapped(turn)
        required_sum = sum(enabling_lands)
        model.add(required_sum >= needed).OnlyEnforceIf(usable_for_colored_mana_var)
        model.add(required_sum < needed).OnlyEnforceIf(usable_for_colored_mana_var.Not())
        makes_mana_var = model.NewIntVar(0, 4, f"{self.name}_Makes_Mana_On_T{turn}")
        model.add(makes_mana_var == land_vars[self]).OnlyEnforceIf(usable_for_colored_mana_var)
        model.add(makes_mana_var == 0).OnlyEnforceIf(usable_for_colored_mana_var.Not())
        return makes_mana_var


@dataclass(eq=True, frozen=True, repr=False)
class Bicycle(Tapland):
    pass

@dataclass(eq=True, frozen=True, repr=False)
class Pain(Land):
    def untapped_rules(self, model: Model, turn: int, land_vars: dict[Land, cp_model.IntVar]) -> cp_model.IntVar | int:
        return land_vars[self]

@dataclass(eq=True, frozen=True, repr=True)
class RiverOfTears(Land):
    # BAKERT complicated to explain this only makes U for instants on t1, and it only makes B on your own turn, and only if you have another land!
    # For now, it's an Underground Sea
    def untapped_rules(self, model: Model, turn: int, land_vars: dict["Land", cp_model.IntVar]) -> cp_model.IntVar | int:
        return land_vars[self]


Wastes = Basic("Wastes", None, "Basic Land", (C,))
Plains = Basic("Plains", None, "Basic Land - Plains", (W,))
Island = Basic("Island", None, "Basic Land - Island", (U,))
Swamp = Basic("Swamp", None, "Basic Land - Swamp", (B,))
Mountain = Basic("Mountain", None, "Basic Land - Mountain", (R,))
Forest = Basic("Forest", None, "Basic Land - Forest", (G,))

# -Wastes
basics = {Plains, Island, Swamp, Mountain, Forest}

ClifftopRetreat = Check("Clifftop Retreat", None, "Land", (R, W))
DragonskullSummit = Check("Dragonskull Summit", None, "Land", (B, R))
DrownedCatacomb = Check("Drowned Catacomb", None, "Land", (U, B))
GlacialFortress = Check("Glacial Fortress", None, "Land", (W, U))
HinterlandHarbor = Check("Hinterland Harbor", None, "Land", (G, U))
IsolatedChapel = Check("Isolated Chapel", None, "Land", (W, B))
RootboundCrag = Check("Rootbound Crag", None, "Land", (R, G))
SulfurFalls = Check("Sulfur Falls", None, "Land", (U, R))
SunpetalGrove = Check("Sunpetal Grove", None, "Land", (G, W))
WoodlandCemetery = Check("Woodland Cemetery", None, "Land", (B, G))

checks = {ClifftopRetreat, DragonskullSummit, DrownedCatacomb, GlacialFortress, HinterlandHarbor, IsolatedChapel, RootboundCrag, SulfurFalls, SunpetalGrove, WoodlandCemetery}

ChokedEstuary = Snarl("Choked Estuary", None, "Land", (U, B))
ForebodingRuins = Snarl("Foreboding Ruins", None, "Land", (B, R))
FortifiedVillage = Snarl("Fortified Village", None, "Land", (G, W))
FrostboilSnarl = Snarl("Frostboil Snarl", None, "Land", (U, R))
FurycalmSnarl = Snarl("Furycalm Snarl", None, "Land", (R, W))
GameTrail = Snarl("Game Trail", None, "Land", (R, G))
NecroblossomSnarl = Snarl("Necroblossom Snarl", None, "Land", (B, G))
PortTown = Snarl("Port Town", None, "Land", (W, U))
ShineshadowSnarl = Snarl("Shineshadow Snarl", None, "Land", (W, B))
VineglimmerSnarl = Snarl("Vineglimmer Snarl", None, "Land", (G, U))

# -FurycalmSnarl, NecroblossomSnarl, ShineshadowSnarl
snarls = {ChokedEstuary, ForebodingRuins, FortifiedVillage, FrostboilSnarl, GameTrail, PortTown, VineglimmerSnarl}

CascadeBluffs = Filter("Cascade Bluffs", None, "Land", (U, R))
FetidHeath = Filter("Fetid Heath", None, "Land", (W, B))
FireLitThicket = Filter("Fire-Lit Thicket", None, "Land", (R, G))
FloodedGrove = Filter("Flooded Grove", None, "Land", (G, U))
GravenCairns = Filter("Graven Cairns", None, "Land", (B, R))
MysticGate = Filter("Mystic Gate", None, "Land", (W, U))
RuggedPrairie = Filter("Rugged Prairie", None, "Land", (R, W))
SunkenRuins = Filter("Sunken Ruins", None, "Land", (U, B))
TwilightMire = Filter("Twilight Mire", None, "Land", (B, G))
WoodedBastion = Filter("Wooded Bastion", None, "Land", (W, G))

# -RuggedPrairie, TwilightMire
filters = {CascadeBluffs, FetidHeath, FireLitThicket, FloodedGrove, GravenCairns, MysticGate, SunkenRuins, WoodedBastion}

CanyonSlough = Bicycle("Canyon Slough", None, "Land - Swamp Mountain", (B, R))
FetidPools = Bicycle("Fetid Pools", None, "Land - Island Swamp", (U, B))
IrrigatedFarmland = Bicycle("Irrigated Farmland", None, "Land - Plains Island", (W, U))
ScatteredGroves = Bicycle("Scattered Groves", None, "Land - Forest Plains", (G, W))
ShelteredThicket = Bicycle("Sheltered Thicket", None, "Land - Mountain Forest", (R, G))

bicycles = {CanyonSlough, FetidPools, IrrigatedFarmland, ScatteredGroves, ShelteredThicket}

CelestialColonnade = Tapland("Celestial Colonnade", None, "Land", (W, U))
CreepingTarPit = Tapland("Creeping Tar Pit", None, "Land", (U, B))
HissingQuagmire = Tapland("Hissing Quagmire", None, "Land", (B, G))
LavaclawReaches = Tapland("Lavaclaw Reaches", None, "Land", (B, R))
LumberingFalls = Tapland("Lumbering Falls", None, "Land", (G, U))
NeedleSpires = Tapland("Needle Spires", None, "Land", (R, W))
RagingRavine = Tapland("Raging Ravine", None, "Land", (R, G))
ShamblingVent = Tapland("Shambling Vent", None, "Land", (W, B))
StirringWildwood = Tapland("Stirring Wildwood", None, "Land", (G, W))
WanderingFumarole = Tapland("Wandering Fumarole", None, "Land", (U, R))

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

GrandColiseum = Tapland("Grand Coliseum", None, "Land", (W, U, B, R, G), painful=True)
# BAKERT need to teach it that the third time you tap vivid crag it only taps for R, tricky
VividCrag = Tapland("Vivid Crag", None, "Land", (W, U, B, R, G))

five_color_lands = {GrandColiseum, VividCrag}

AdarkarWastes = Pain("Adarkar Wastes", None, "Land", (W, U), painful=True)
BattlefieldForge = Pain("Battlefield Forge", None, "Land", (R, W), painful=True)
Brushland = Pain("Brushland", None, "Land", (G, W), painful=True)
CavesOfKoilos = Pain("Caves of Koilos", None, "Land", (W, B), painful=True)
KarplusanForest = Pain("Karplusan Forest", None, "Land", (R, G), painful=True)
LlanowarWastes = Pain("Llanowar Wastes", None, "Land", (B, G), painful=True)
ShivanReef = Pain("Shivan Reef", None, "Land", (U, R), painful=True)
SulfurousSprings = Pain("Sulfurous Springs", None, "Land", (B, R), painful=True)
UndergroundRiver = Pain("Underground River", None, "Land", (U, B), painful=True)
YavimayaCoast = Pain("Yavimaya Coast", None, "Land", (G, U), painful=True)

# -AdarkarWastes,  UndergroundRiver
painlands = {BattlefieldForge, Brushland, CavesOfKoilos, KarplusanForest, LlanowarWastes, ShivanReef, SulfurousSprings, YavimayaCoast}

# BAKERT PrairieStream and the GW one

CrumblingNecropolis = Tapland("Crumbling Necropolis", None, "Land", (U, B, R))
RiverOfTears = RiverOfTears("River of Tears", None, "Land", (U, B))

# BAKERT Tendo Ice Bridge and Crumbling Vestige

# no creaturelands for now for speed
all_lands: set[Land] = basics.union(checks).union(snarls).union(bicycles).union(filters).union(five_color_lands).union(painlands).union({CrumblingNecropolis, RiverOfTears})

@dataclass(eq=True, frozen=True, order=True)
class Constraint:
    required: ManaCost
    turn: int = -1

    def __post_init__(self) -> None:
        if self.turn == -1:
            object.__setattr__(self, "turn", self.required.mana_value)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"T{self.turn} {self.required}"

def card(spec: str, turn: int | None = None) -> Constraint:
    colors, generic = [], 0
    for i in range(len(spec) - 1, -1, -1):
        c = spec[i]
        if c.isnumeric():
            generic = int(spec[0:i + 1])
            break
        colors.insert(0, next(color for color in all_colors if color.code == c))
    parts = ([generic] if generic else []) + colors
    return Constraint(ManaCost(*parts), turn if turn else generic + len(colors))

# BAKERT need some way to say "the manabase must include 4 Shelldock Isle"
def solve(constraints: list[Constraint]) -> None:
    model = define_model(constraints)
    solver = cp_model.CpSolver()
    status = solver.solve(model.model)
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("Solution found (" + ("not " if status != cp_model.OPTIMAL else "") + "optimal):")
        for constraint in constraints:
            print(constraint)
        print()
        gap = False
        for var in model.vars:
            if "_" in var.name and not gap:
                print()
                gap = True
            if model.debug or (solver.Value(var) > 0 and "_" not in var.name):
                print(f"{var.name}: {solver.Value(var)}")
    else:
        print("No solution found")


def define_model(constraints: list[Constraint]) -> Model:
    model = Model()
    colors = find_colors(constraints)
    possible_lands = viable_lands(colors, all_lands)
    land_vars = {land: model.NewIntVar(0, land.max, land.name) for land in possible_lands}

    # Make sure we have enough colored sources to cast our spells the turn we want to cast them
    for constraint in constraints:
        required = frank(constraint)
        # BAKERT this doesn't account for the fact that a 1UW card can't count the same land for U and for W
        for color, n in required.items():
            sources = sum(land_vars[land] for land in possible_lands if land.can_produce(color))
            model.add(sources >= n)
        generic_ok = len(constraint.required.pips) > len(constraint.required.colored_pips)
        need = need_untapped(constraint.turn)
        admissible_untapped = {land: var for land, var in land_vars.items() if generic_ok or any(color in land.produces for color in required)}
        # is the third arg to untapped_rules land_vars, or admissible_untapped? I think land_vars?
        untapped_this_turn = sum(land.untapped_rules(model, constraint.turn, land_vars) for land in admissible_untapped)
        model.add(untapped_this_turn >= need)

    min_lands = max(num_lands_required(constraint) for constraint in constraints)
    total_lands = model.NewIntVar(0, 100, "Total Lands")
    model.add(total_lands == sum(land_vars.values()))
    model.add(total_lands >= min_lands)

    # Hint to the model that having more untapped mana is better than having less over the first N turns of the game
    mana_spend = model.NewIntVar(0, 100, "Mana Spend")
    max_mana_spend = model.NewIntVar(0, 100, "Max Mana Spend")
    max_mana_spend_per_turn, mana_spend_per_turn = [], []
    max_turn = max(constraint.turn for constraint in constraints) + 1
    for turn in range(1, max_turn):
        # BAKERT the other place where we do this kind of thing we use admissible_untapped not land_vars … is this a bug? Does it matter?
        untapped_this_turn = sum(land.untapped_rules(model, turn, land_vars) for land in land_vars)
        # BAKERT this isn't quite right it's kind of 1, turn (independently executed) and it's kind of turn, turn (if you spent every turn so far)
        needed = num_lands(turn, turn)
        enough_untapped = model.NewBoolVar(f"can_spend_mana_t{turn}")
        model.add(untapped_this_turn >= needed).OnlyEnforceIf(enough_untapped)
        model.add(untapped_this_turn < needed).OnlyEnforceIf(enough_untapped.Not())
        max_mana_spend_this_turn = model.NewIntVar(turn, turn, f"max_mana_spend_t{turn}")
        model.add(max_mana_spend_this_turn == turn)
        max_mana_spend_per_turn.append(max_mana_spend_this_turn)
        mana_spend_this_turn = model.NewIntVar(turn - 1, turn, f"mana_spend_t{turn}")
        model.add(mana_spend_this_turn == turn).OnlyEnforceIf(enough_untapped)
        model.add(mana_spend_this_turn == turn - 1).OnlyEnforceIf(enough_untapped.Not())
        mana_spend_per_turn.append(mana_spend_this_turn)
    model.add(max_mana_spend == sum(max_mana_spend_per_turn))
    model.add(mana_spend == sum(mana_spend_per_turn))

    # BAKERT this should maybe be modeled as pain spent in first N turns rather than just how many painlands
    # BAKERT t1 combo don't care about pain, t20 control cares a lot, I think?
    pain = model.NewIntVar(0, 100, "Pain")  # BAKERT 100 has snuck in as a magic number in some places
    model.add(pain == sum(land_vars[land] for land in possible_lands if land.painful))

    # Give a little credit for extra sources. if you can double spell sometimes more your manabase is better
    all_colored_sources = []
    for color in colors:
        contributing_lands = sum([var for land, var in land_vars.items() if color in land.produces])
        colored_sources = model.NewIntVar(0, MAX_DECK_SIZE, f'Sources of {color}')
        model.add(colored_sources == contributing_lands)
        all_colored_sources.append(contributing_lands)
    total_colored_sources = model.NewIntVar(0, MAX_DECK_SIZE, f'Total Colored Sources')
    model.add(total_colored_sources == sum(all_colored_sources))

    # BAKERT if a deck is playing 5+ drops it cares less about fitting in 24 lands than a deck curving out to 4
    model.Maximize(mana_spend * 100 - total_lands * 1000 - pain + total_colored_sources * 10)

    return model


def find_colors(constraints: list[Constraint]) -> set[Color]:
    colors = set()
    for constraint in constraints:
        for pip in constraint.required.colored_pips:
            colors.add(pip)
    return colors


def viable_lands(colors: set[Color], lands: set[Land]) -> set[Land]:
    possible_lands = set()
    for land in lands:
        # BAKERT some simplifying pd-specific assumptions here about what lands we might be interested in
        if len(colors) <= 2 and len(land.produces) > 2:
            continue
        if len(colors.intersection(land.produces)) >= 2 or (colors.intersection(land.produces) and isinstance(land, Basic)):
            possible_lands.add(land)
    return possible_lands


# BAKERT or is it better to use this? https://www.channelfireball.com/article/How-Many-Lands-Do-You-Need-in-Your-Deck-An-Updated-Analysis/cd1c1a24-d439-4a8e-b369-b936edb0b38a/
# 19.59 + 1.90 * average mana value – 0.28 * number of cheap card draw or mana ramp spells + 0.27 * companion count
def num_lands_required(constraint: Constraint) -> int:
    return num_lands(constraint.required.mana_value, constraint.turn)


def need_untapped(turn: int) -> int:
    try:
        return frank(Constraint(ManaCost(C), turn))[C]
    except UnsatisfiableConstraint:
        # We don't know how many untapped lands you need beyond turn 6 so supply an overestimate
        return frank(Constraint(ManaCost(C), 6))[C]


class UnsatisfiableConstraint(Exception):
    pass


# https://www.channelfireball.com/article/how-many-sources-do-you-need-to-consistently-cast-your-spells-a-2022-update/dc23a7d2-0a16-4c0b-ad36-586fcca03ad8/
def frank(constraint: Constraint, deck_size: int = 60) -> dict[Color, int]:
    table = {
        (1, 1): {60: 14, 80: 19, 99: 19, 40: 9},  # C Monastery Swiftspear
        (1, 2): {60: 13, 80: 18, 99: 19, 40: 9},  # 1C Ledger Shredder
        (2, 2): {60: 21, 80: 28, 99: 30, 40: 14},  # CC Lord of Atlantis
        (1, 3): {60: 12, 80: 16, 99: 18, 40: 8},  # 2C Reckless Stormseeker
        (2, 3): {60: 18, 80: 25, 99: 28, 40: 12},  # 1CC Narset, Parter of Veils
        (3, 3): {60: 23, 80: 32, 99: 36, 40: 16},  # CCC Goblin Chainwhirler
        (1, 4): {60: 10, 80: 15, 99: 16, 40: 7},  # 3C Collected Company
        (2, 4): {60: 16, 80: 23, 99: 26, 40: 11},  # 2CC Wrath of God
        (3, 4): {60: 21, 80: 29, 99: 33, 40: 14},  # 1CCC Cryptic Command
        (4, 4): {60: 24, 80: 34, 99: 39, 40: 17},  # CCCC Dawn Elemental
        (1, 5): {60: 9, 80: 14, 99: 15, 40: 6},  # 4C Doubling Season
        (2, 5): {60: 15, 80: 20, 99: 23, 40: 10},  # 3CC  Baneslayer Angel
        (3, 5): {60: 19, 80: 26, 99: 30, 40: 13},  # 2CCC Garruk, Primal Hunter
        (4, 5): {60: 22, 80: 31, 99: 36, 40: 15},  # 1CCCC Unnatural Growth
        (1, 6): {60: 9, 80: 12, 99: 14, 40: 6},  # 5C Drowner of Hope
        (2, 6): {60: 13, 80: 19, 99: 22, 40: 9},  # 4CC Primeval Titan
        (3, 6): {60: 16, 80: 22, 99: 26, 40: 10},  # 3CCC Massacre Wurm
        (2, 7): {60: 12, 80: 17, 99: 20, 40: 8},  # 5CC Hullbreaker Horror
        (3, 7): {60: 16, 80: 22, 99: 26, 40: 10},  # 4CCC Nyxbloom Ancient
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


def num_lands(mana_value: int, turn: int) -> int:
    try:
        return frank(Constraint(turn=turn, required=ManaCost(*[W] * mana_value)))[W]
    except UnsatisfiableConstraint:
        # We are at mana value 5 or beyond, return an underestimate, but better than nothing
        return frank(Constraint(turn=4, required=ManaCost(*[W] * 4)))[W]


DeputyOfDetention = Constraint(ManaCost(1, U, W), 3)

BurstLightningOnTurnTwo = Constraint(ManaCost(R), 2)
BurstLightning = card("R")
MemoryLapse = Constraint(ManaCost(1, U), 2)
PestermiteOnTurnFour = Constraint(ManaCost(2, U), 4)
RestorationAngel = Constraint(ManaCost(3, W))
KikiJikiMirrorBreaker = Constraint(ManaCost(2, R, R, R), 5)
Disenchant = Constraint(ManaCost(1, W), 2)
LightningHelix = card("RW")
Forbid = Constraint(ManaCost(1, U, U), 3)
OptOnTurnTwo = card("U", 2)
Pestermite = card("2U")
AncestralVision = card("U")

jeskai_twin = [BurstLightningOnTurnTwo, LightningHelix, MemoryLapse, Pestermite, RestorationAngel, KikiJikiMirrorBreaker]

BenevolentBodyguard = Constraint(ManaCost(W), 1)
MeddlingMage = Constraint(ManaCost(U, W), 2)
SamuraiOfThePaleCurtain = Constraint(ManaCost(W, W), 2)

azorius_taxes = [BenevolentBodyguard, MeddlingMage, SamuraiOfThePaleCurtain, DeputyOfDetention]

SettleTheWreckage = Constraint(ManaCost(2, W, W), 4)
VenserShaperSavant = card("2UU")

azorius_taxes_postboard = azorius_taxes + [SettleTheWreckage]

mono_w_bodyguards = [BenevolentBodyguard]
white_weenie = [BenevolentBodyguard, SamuraiOfThePaleCurtain]
meddlers = [BenevolentBodyguard, MeddlingMage]

InvasionOfAlara = Constraint(ManaCost(W, U, B, R, G), 5)
invasion_of_alara = [InvasionOfAlara]

Duress = card("B")
Abrade = card("1R")
DigThroughTime = card("UU", 5)
WrathOfGod = card("2WW", 4)

popular = [MemoryLapse, Abrade, DigThroughTime, WrathOfGod]

BaskingRootwalla = card("G")
PutridImp = card("B")
LotlethTroll = card("BG")
LotlethTrollWithRegen = card("BBG")

golgari_madness = [PutridImp, LotlethTroll]

GrimLavamancer = card("R")
Pteramander = card("U")
LogicKnot = card("1UU")

gfabsish = [GrimLavamancer, Pteramander, VenserShaperSavant]

Assault = card("R", 2)
LagoonBreach = card("1U")
MadcapExperiment = card("3R")
Away = card("2B")
ChainOfPlasma = card("1R")

my_invasion_of_alara = [Assault, LagoonBreach, MadcapExperiment, Away, InvasionOfAlara, ChainOfPlasma]

GiantKiller = card("W")
KnightOfTheWhiteOrchid = card("WW")
SunTitan = card("4WW")

emeria = [GiantKiller, KnightOfTheWhiteOrchid, SunTitan]

PriestOfFellRites = card("WB")
HaakonStromgaldScourge = card("1BB", 5)
MagisterOfWorth = card("4WB")
OptOnTurn2 = card("U", 2)
SearchForAzcanta = card("1U")
CouncilsJudgment = card("1WW", 4)
EsperCharm = card("WUB")
ForbidOnTurnFour = card("1UU", 4)
WrathOfGod = card("2WW")

# BAKERT River of Tears

gifts = [PriestOfFellRites, HaakonStromgaldScourge, MagisterOfWorth, OptOnTurn2, SearchForAzcanta, CouncilsJudgment, EsperCharm, ForbidOnTurnFour, WrathOfGod]

actual_twin = [GrimLavamancer, Pteramander, KikiJikiMirrorBreaker, DigThroughTime]

# Crypt of Agadeem possibly beyond simulation :)
LamplightPhoenix = card("1RR")
BigCyclingTurn = card("BBB")
BringerOfTheLastGift = card("6BB")
StarvingRevenant = card("2BB")
ArchfiendOfIfnir = card("3BB")

midnight_phoenix = [LamplightPhoenix, BigCyclingTurn, StarvingRevenant, ArchfiendOfIfnir]

Opt = card("U")
SwelteringSuns = card("1RR")
CracklingDrake = card("UURR")

izzet_twin = [Opt, BurstLightning, Pestermite, CracklingDrake, SwelteringSuns, DigThroughTime, KikiJikiMirrorBreaker]

Cremate = card("B")
GlimpseTheUnthinkable = card("UB")

mill = [Cremate, GlimpseTheUnthinkable, DigThroughTime]

HomeForDinner = card("1W")
GeologicalAppraiser = card("2RR")
SuspendGlimpseOnTwo = card("RR")
SuspendGlimpseOnThree = card("RR", 3)
CavalierOfDawn = card("2WWW")
ChancellorOfTheForge = card("4RRR")
EtalisFavor = card("2R")

glimpse = [HomeForDinner, GeologicalAppraiser, EtalisFavor]

SeismicAssault = card("RRR")
SwansOfBrynArgoll = card("2UU")

seismic_swans = [SeismicAssault, SwansOfBrynArgoll]

NecroticOoze = card("2BB")
GiftsUngiven = card("3U")
TaintedIndulgence = card("UB")

ooze = [NecroticOoze, PriestOfFellRites, TaintedIndulgence]

BloodsoakedChampion = card("B")
UnluckyWitness = card("R")
DreadhordeButcher = card("BR")
LightningSkelemental = card("BRR")

skelemental_sac = [BloodsoakedChampion, UnluckyWitness, DreadhordeButcher, LightningSkelemental]

def test_viable_lands() -> None:
    lands = {Plains, Island, Swamp, CelestialColonnade, StirringWildwood, CreepingTarPit}
    assert viable_lands({W, U}, lands) == {Plains, Island, CelestialColonnade}


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


def test() -> None:
    test_viable_lands()
    test_str_repr()
    test_basic_land_types()


if len(sys.argv) >= 2 and (sys.argv[1] == "--test" or sys.argv[1] == "-t"):
    test()
else:
    solve(midnight_phoenix)

# BAKERT you should never choose Crumbling Necropolis over a check or a snarl in UR (or UB or RB)
# BAKERT in general you should be able to get partial credit for a check or a snarl even if not hitting the numbers

# BAKERT
# Phyrexian mana
# Hybrid mana
# Snow mana and snow lands and snow-covered basics
# Yorion
# Commander
# Limited
