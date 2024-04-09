from dataclasses import dataclass, field
from enum import Enum
from functools import total_ordering
from typing import Iterable, Literal
import sys

from more_itertools import powerset
from multiset import FrozenMultiset
from ortools.sat.python import cp_model

from remembering_model import KeyCollision, RememberingModel

MAX_DECK_SIZE = 100


@dataclass(frozen=True)
@total_ordering
class Color:
    code: str
    name: str

    @property
    def _value(self) -> int:
        return {"W": 1, "U": 2, "B": 3, "R": 4, "G": 5, "C": 6}[self.code]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return self._value == other._value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return self._value < other._value

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


class ColorCombination(FrozenMultiset):
    def __repr__(self) -> str:
        return "".join(str(c) for c in list(self))

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
@total_ordering
class ManaCost:
    pips: tuple[Color | int, ...]

    def __init__(self, *args: Color | int) -> None:
        object.__setattr__(self, "pips", args)

    @property
    def mana_value(self) -> int:
        return sum(1 if isinstance(pip, Color) else pip for pip in self.pips)

    @property
    def colored_pips(self) -> tuple[Color, ...]:
        return tuple(pip for pip in self.pips if isinstance(pip, Color))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ManaCost):
            return NotImplemented
        return self.mana_value == other.mana_value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ManaCost):
            return NotImplemented
        return self.mana_value < other.mana_value

    def __repr__(self) -> str:
        return "".join(str(pip) for pip in self.pips)

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(eq=True, frozen=True, order=True)
class Constraint:
    required: ManaCost
    turn: int = -1

    def color_combinations(self) -> frozenset[ColorCombination]:
        return find_color_combinations(self.required.colored_pips)

    def __post_init__(self) -> None:
        if self.turn == -1:
            object.__setattr__(self, "turn", self.required.mana_value)

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"T{self.turn} {self.required}"


IntVar = cp_model.IntVar | int
Contributions = dict[ColorCombination, IntVar]
UNTAPPED = "untapped"
Untapped = Literal["untapped"]
Resource = ColorCombination | Untapped
ResourceVars = dict[Resource, list[IntVar]]
ConstraintVars = dict[Constraint, ResourceVars]


class Model(RememberingModel):
    def __init__(self, possible_lands: frozenset["Land"], debug: bool = False):
        super().__init__(debug)
        self.lands = {land: self.new_int_var(0, land.max, (land,)) for land in possible_lands}
        # vars: list[ModelVar] = field(default_factory=list) BAKERT we must expose self.model.store the same way we exposed vars for full debug mode read everything
        self.min_lands = self.new_int_var(0, MAX_DECK_SIZE, ("min_lands",))
        self.mana_spend = self.new_int_var(0, 100, ("mana_spend",))
        self.max_mana_spend = self.new_int_var(0, 100, ("max_mana_spend",))
        self.total_lands = self.new_int_var(0, MAX_DECK_SIZE, ("total_lands",))
        self.pain = self.new_int_var(0, 100, ("pain",))  # BAKERT 100 has snuck in as a magic number in some places
        self.objective = self.new_int_var(-10000, 10000, ("objective",))  # BAKERT magic number
        self.has: dict[tuple[int, Resource], cp_model.IntVar] = {}  # self.has: dict[tuple[int, Resource], IntVar] = field(default_factory=dict, init=False)
        self.required: dict[tuple[int, Resource], cp_model.IntVar] = {}  # self.required: dict[tuple[int, Resource], IntVar] = field(default_factory=dict, init=False)
        self.sources: dict[tuple[int, Resource], cp_model.IntVar] = {}  # self.sources: dict[tuple[int, Resource], IntVar] = field(default_factory=dict, init=False)
        self.providing: dict[tuple[int, Resource], list[IntVar]] = {}  # self.providing: dict[tuple[int, Resource], list[IntVar]] = field(default_factory=dict, init=False)

    def new_required(self, turn: int, resource: Resource) -> cp_model.IntVar:
        v = self.new_int_var(0, MAX_DECK_SIZE, (turn, resource, "required"))
        self.required[(turn, resource)] = v
        return v  # BAKERT could make all these two lines by assigning into the dict and returning a get from the dict?

    def new_sources(self, turn: int, resource: Resource) -> cp_model.IntVar:
        v = self.new_int_var(0, MAX_DECK_SIZE, (turn, resource, "sources"))  # BAKERT near-identical to required
        # BAKERT should we complain if we've seen this exact intvar before? any needs?
        self.sources[(turn, resource)] = v
        return v  # BAKERT we could check for prior existence and not bother if found?

    # BAKERT providing is kind of weird … why is it even necessary?
    # BAKERT it's possible we want to change the behavior of `add` (and `NewIntVar`/`NewBoolVar`??) to store basically everything rather the explicitly calling remember
    # BAKERT this is not quite right "4 Fetid Heath 4"
    def new_providing(self, turn: int, resource: Resource, sources: list[IntVar]) -> None:
        self.providing[(turn, resource)] = sources


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


class Zone(Enum):
    HAND = "Hand"
    BATTLEFIELD = "Battlefield"


@dataclass(frozen=True)
class Card:
    name: str
    mana_cost: ManaCost | None
    typeline: str

    @property
    def max(self) -> int:
        # Some cards break this rule and have specific rules text to say so, including Seven Dwarves as well as unlimited
        return MAX_DECK_SIZE if self.is_basic else 4

    @property
    def is_basic(self) -> bool:
        return self.typeline.startswith("Basic Land")

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other: "Card") -> bool:
        return self.name < other.name


@dataclass(frozen=True, repr=False)
@total_ordering
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

    def can_produce_any(self, colors: Iterable[Color]) -> bool:
        return any(c in self.produces for c in colors)

    def has_basic_land_types(self, basic_land_types: frozenset[BasicLandType]) -> bool:
        for basic_land_type in basic_land_types:
            if basic_land_type in self.basic_land_types:
                return True
        return False

    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        raise NotImplementedError

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Land):
            return NotImplemented
        return self == other

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Land):
            return NotImplemented
        return self.produces < other.produces or (self.produces == other.produces and self.name < other.name)


class Conditional(Land):
    def untapped_if(self, model: Model, turn: int, needed: int, enablers: cp_model.LinearExprT, land_var: cp_model.IntVar) -> cp_model.IntVar:
        untapped_var = model.new_bool_var((self, turn, UNTAPPED))
        model.add(enablers >= needed).OnlyEnforceIf(untapped_var)  # type: ignore
        model.add(enablers < needed).OnlyEnforceIf(untapped_var.Not())
        makes_mana_var = model.new_int_var(0, 4, (self, turn))
        model.add(makes_mana_var == land_var).OnlyEnforceIf(untapped_var)
        model.add(makes_mana_var == 0).OnlyEnforceIf(untapped_var.Not())
        return makes_mana_var


@dataclass(eq=True, frozen=True, repr=False)
class Basic(Land):
    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        return model.lands[self]

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if self.can_produce_any(color_combination):
                contributions[color_combination] = model.lands[self]
            else:
                contributions[color_combination] = 0
        return contributions


@dataclass(eq=True, frozen=True, repr=False)
class Tapland(Land):
    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        return 0

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if constraint.turn > 1 and self.can_produce_any(color_combination):
                contributions[color_combination] = model.lands[self]
            else:
                contributions[color_combination] = 0
        return contributions


@dataclass(eq=True, frozen=True, repr=False)
class BasicTypeCaring(Conditional):
    basic_land_types_needed: frozenset[BasicLandType] = field(default_factory=frozenset, init=False)
    zone: Zone = field(default=Zone.HAND, init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        needed = frozenset({basic_land_type for basic_land_type in all_basic_land_types if basic_land_type.produces in self.produces})
        object.__setattr__(self, "basic_land_types_needed", needed)

    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        if self.zone == Zone.BATTLEFIELD and turn == 1:
            return 0
        enabling_lands = {var for land, var in model.lands.items() if land.has_basic_land_types(self.basic_land_types_needed)}
        # This crudely models the difficulty of playing a Snarl untapped after t1 but overestimates that difficulty by assuming you always play an enabling land each turn
        needed = need_untapped(turn) if self.zone == Zone.BATTLEFIELD else num_lands(turn, turn)
        enablers = sum(enabling_lands)
        return self.untapped_if(model, turn, needed, enablers, model.lands[self])

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if self.can_produce_any(color_combination):
                contributions[color_combination] = model.lands[self]
            else:
                contributions[color_combination] = 0
        return contributions


@dataclass(eq=True, frozen=True, repr=False)
class Check(BasicTypeCaring):
    zone: Zone = field(default=Zone.BATTLEFIELD, init=False)


@dataclass(eq=True, frozen=True, repr=False)
class Snarl(BasicTypeCaring):
    zone: Zone = field(default=Zone.HAND, init=False)


@dataclass(eq=True, frozen=True, repr=False)
class Filter(Conditional):
    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        if turn <= 1:
            return 0
        enabling_lands = []
        for land, var in model.lands.items():
            # BAKERT If your hand is ALL filters then you can't get kickstarted on t3+ either, and we don't account for that here
            # On the other hand if we exclude filters on turn 3+ then we miss going Island -> Sunken Ruins -> Fetid Heath for W
            if turn <= 2 and isinstance(land, Filter):
                continue
            if self.can_produce_any(land.produces):
                enabling_lands.append(var)
        needed = need_untapped(turn)
        enablers = sum(enabling_lands)
        return self.untapped_if(model, turn, needed, enablers, model.lands[self])  # BAKERt rmeove this param in favor of reading it from model

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        m, n, _ = self.produces
        land_var = model.lands[self]
        contributions: Contributions = {}

        # Eject early saying we can only make colorless mana if it's turn 1, or we don't make any of the colors requested.
        if constraint.turn == 1 or not any(self.can_produce_any(c) for c in constraint.color_combinations()):
            return {color_combination: land_var if C in color_combination else 0 for color_combination in constraint.color_combinations()}

        c_sources = model.new_int_var(0, self.max, (self, constraint))  # BAKERT Constraint should never be in key - just provide the turn and the resource?
        model.add(c_sources <= land_var)  # BAKERT this needs to be mutex with the colored stuff
        mm_sources = model.new_int_var(0, self.max * 2, (self, constraint, f"{m}{m}"))
        model.add(mm_sources <= land_var * 2)
        mn_sources = model.new_int_var(0, self.max * 2, (self, constraint, f"{m}{n}"))
        model.add(mn_sources <= land_var * 2)
        nn_sources = model.new_int_var(0, self.max * 2, (self, constraint, f"{n}{n}"))
        model.add(nn_sources <= land_var * 2)
        m_consumed = model.new_int_var(0, self.max, (self, constraint, f"{m} consumed"))
        n_consumed = model.new_int_var(0, self.max, (self, constraint, f"{n} consumed"))
        model.add(m_consumed <= land_var)
        model.add(n_consumed <= land_var)
        model.add((m_consumed + n_consumed) * 2 == mm_sources + mn_sources + nn_sources)
        model.add(mm_sources + mn_sources + nn_sources - m_consumed - n_consumed == land_var)  # type: ignore
        active = model.new_bool_var((self, constraint, "can make colored mana"))

        # BAKERT exclude other filterlands if turn 2, but it gets more complicated after that
        # BAKERT consider giving this and basically everything a variable name for greater debuggability
        # BAKERT this is essentially repeated code from untapped_rules, but actually we're enforcing slightly different logic there!
        enablers = sum(var for land, var in model.lands.items() if land.can_produce_any({m, n}) and not isinstance(land, Filter))
        required = need_untapped(constraint.turn)  # BAKERT need_untapped now a bad name for this func
        model.add(enablers >= required).OnlyEnforceIf(active)
        model.add(enablers < required).OnlyEnforceIf(active.Not())
        # BAKERT we do have to say that you can't make M or N if you're not active but the way we were doing that was linking it to mystic_gate and that's not right, maybe other requirements will want you to include it on other turns
        # model.add(w_sources == land_var)
        # model.add(u_sources == land_var)
        # model.add(w_sources == 0).OnlyEnforceIf(active.Not())
        # model.add(u_sources == 0).OnlyEnforceIf(active.Not())
        model.add(mm_sources == 0).OnlyEnforceIf(active.Not())  # BAKERT it's really annoying you can't see the OnlyEnforceIfs in the debug output, maybe we could wrap the return value and proxy along to it? pretty grim
        model.add(mn_sources == 0).OnlyEnforceIf(active.Not())
        model.add(nn_sources == 0).OnlyEnforceIf(active.Not())

        # A Mystic Gate can't help cast a spell with all colored pips where one or more of the pips is not W or U
        impossible_turn_2_contribution = constraint.turn == 2 and len(constraint.required.colored_pips) == 2 and any(c not in self.produces for c in constraint.required.colored_pips)

        # BAKERT we must *remove* the w consumed and the u consumed from any double cost or higher
        for color_combination in constraint.color_combinations():
            # BAKERT how does this behave when we have WWUU? we just arbitrarily decide to contribute to WW? That seems wrong.
            if color_combination[m] >= 2:
                contributions[color_combination] = mm_sources
            elif color_combination[m] and color_combination[n]:
                contributions[color_combination] = mn_sources
            elif color_combination[n] >= 2:
                contributions[color_combination] = nn_sources
            elif (color_combination == ColorCombination([m]) or color_combination == ColorCombination([n])) and not impossible_turn_2_contribution:
                contributions[color_combination] = land_var  # BAKERT not if it isn't enabled
            elif C in color_combination:
                contributions[color_combination] = land_var
        return contributions


@dataclass(eq=True, frozen=True, repr=False)
class Bicycle(Tapland):
    pass


@dataclass(eq=True, frozen=True, repr=False)
class Pain(Land):
    painful: bool = True

    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        return model.lands[self]

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if self.can_produce_any(color_combination):
                contributions[color_combination] = model.lands[self]
            else:
                contributions[color_combination] = 0
        return contributions


# BAKERT complicated to explain this only makes U for instants on t1, and it only makes B on your own turn, and only if you have another land! For now, it's an Underground Sea
@dataclass(eq=True, frozen=True, repr=False)
class RiverOfTearsLand(Land):
    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        return model.lands[self]

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if U in color_combination or B in color_combination:
                contributions[color_combination] = model.lands[self]
        return contributions


@dataclass(eq=True, frozen=True, repr=False)
class Tango(Conditional):
    def untapped_rules(self, model: Model, turn: int) -> IntVar:
        if turn <= 2:
            return 0
        needed = num_lands(2, turn - 1)
        enablers = sum(var for land, var in model.lands.items() if land.is_basic)
        return self.untapped_if(model, turn, needed, enablers, model.lands[self])

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        # BAKERT add_to_model and untapped_rules kind of counterfeit one another, can we combine them?
        if constraint.turn == 1:
            return {color_combination: 0 for color_combination in constraint.color_combinations()}
        return {color_combination: model.lands[self] if self.can_produce_any(color_combination) else 0 for color_combination in constraint.color_combinations()}


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

CascadeBluffs = Filter("Cascade Bluffs", None, "Land", (U, R, C))
FetidHeath = Filter("Fetid Heath", None, "Land", (W, B, C))
FireLitThicket = Filter("Fire-Lit Thicket", None, "Land", (R, G, C))
FloodedGrove = Filter("Flooded Grove", None, "Land", (G, U, C))
GravenCairns = Filter("Graven Cairns", None, "Land", (B, R, C))
MysticGate = Filter("Mystic Gate", None, "Land", (W, U, C))
RuggedPrairie = Filter("Rugged Prairie", None, "Land", (R, W, C))
SunkenRuins = Filter("Sunken Ruins", None, "Land", (U, B, C))
TwilightMire = Filter("Twilight Mire", None, "Land", (B, G, C))
WoodedBastion = Filter("Wooded Bastion", None, "Land", (W, G, C))

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

# -CreepingTarPit
creature_lands = {CelestialColonnade, HissingQuagmire, LavaclawReaches, LumberingFalls, NeedleSpires, RagingRavine, ShamblingVent, StirringWildwood, WanderingFumarole}

RestlessAnchorage = Tapland("Restless Anchorage", None, "Land", (U, W))
RestlessBivouac = Tapland("Restless Bivouac", None, "Land", (R, W))
RestlessCottage = Tapland("Restless Cottage", None, "Land", (B, G))
RestlessFortress = Tapland("Restless Fortress", None, "Land", (W, B))
RestlessPrairie = Tapland("Restless Prairie", None, "Land", (G, W))
RestlessReef = Tapland("Restless Reef", None, "Land", (U, B))
RestlessRidgeline = Tapland("Restless Ridgeline", None, "Land", (R, G))
RestlessSpire = Tapland("Restless Spire", None, "Land", (U, R))
RestlessVents = Tapland("Restless Vents", None, "Land", (B, R))
RestlessVinestalk = Tapland("Restless Vinestalk", None, "Land", (G, U))

# -RestlessAnchorage, RestlessBivouac, RestlessCottage, RestlessReef, RestlessSpire
restless_lands = {RestlessFortress, RestlessPrairie, RestlessRidgeline, RestlessVents, RestlessVinestalk}

GrandColiseum = Tapland("Grand Coliseum", None, "Land", (W, U, B, R, G), painful=True)
# BAKERT need to teach it that the third time you tap vivid crag it only taps for R, tricky
VividCrag = Tapland("Vivid Crag", None, "Land", (W, U, B, R, G))

five_color_lands = {GrandColiseum, VividCrag}

AdarkarWastes = Pain("Adarkar Wastes", None, "Land", (W, U))
BattlefieldForge = Pain("Battlefield Forge", None, "Land", (R, W))
Brushland = Pain("Brushland", None, "Land", (G, W))
CavesOfKoilos = Pain("Caves of Koilos", None, "Land", (W, B))
KarplusanForest = Pain("Karplusan Forest", None, "Land", (R, G))
LlanowarWastes = Pain("Llanowar Wastes", None, "Land", (B, G))
ShivanReef = Pain("Shivan Reef", None, "Land", (U, R))
SulfurousSprings = Pain("Sulfurous Springs", None, "Land", (B, R))
UndergroundRiver = Pain("Underground River", None, "Land", (U, B))
YavimayaCoast = Pain("Yavimaya Coast", None, "Land", (G, U))

# -AdarkarWastes,  UndergroundRiver
painlands = {BattlefieldForge, Brushland, CavesOfKoilos, KarplusanForest, LlanowarWastes, ShivanReef, SulfurousSprings, YavimayaCoast}

PrairieStream = Tango("Prairie Stream", None, "Land - Plains Island", (W, U))
CanopyVista = Tango("Canopy Vista", None, "Land - Forest Plains", (G, W))

tangos = {PrairieStream, CanopyVista}

CrumblingNecropolis = Tapland("Crumbling Necropolis", None, "Land", (U, B, R))
RiverOfTears = RiverOfTearsLand("River of Tears", None, "Land", (U, B))

# BAKERT Tendo Ice Bridge and Crumbling Vestige

all_lands = frozenset(basics.union(checks).union(snarls).union(bicycles).union(filters).union(five_color_lands).union(painlands).union({CrumblingNecropolis, RiverOfTears}).union(tangos).union(creature_lands).union(restless_lands))


# BAKERT Solution is such a mirror of Model that I wonder if they should be combined
@dataclass
class Solution:
    constraints: frozenset[Constraint]  # BAKERT don't thse live on model? should they?
    status: int
    model: Model
    solver: cp_model.CpSolver
    # vars: dict[str, int]
    # store: ConstraintVars
    # debug: bool = False
    lands: dict[Land, int] = field(default_factory=dict, init=False)
    min_lands: int = field(init=False)
    mana_spend: int = field(init=False)
    max_mana_spend: int = field(init=False)
    pain: int = field(init=False)
    objective: int = field(init=False)
    # BAKERT keys are all str, but probably shouldn't be as they are truly Constraints and ColorCombinations
    # BAKERT it'd be nice to say Turn instead of int in a bunch of places
    # BAKERT typing workd
    required: dict[tuple[int, Resource], int] = field(default_factory=dict, init=False)
    sources: dict[tuple[int, Resource], int] = field(default_factory=dict, init=False)
    # BAKERT store and untapped are in a sense the same thing, combine them or just do better with all this in general?
    # untapped: dict[Constraint | str, int] = field(default_factory=dict, init=False)
    # BAKERT at bottom we still have a list of strs here, would be nice to have something more structured
    providing: dict[tuple[int, Resource], list[str]] = field(default_factory=dict, init=False)  # BAKERT typing work for lands with count

    def __post_init__(self) -> None:
        self.lands = {land: self.solver.Value(var) for land, var in self.model.lands.items() if self.solver.Value(var) > 0}
        self.min_lands = self.solver.Value(self.model.min_lands)  # BAKERT I bet model.get is no longer in use?
        # BAKERT get should probably be structured with turn, resource and key fields
        # BAKERT pushing knowledge of how to form keys in here is bad
        self.mana_spend = self.solver.Value(self.model.mana_spend)
        self.max_mana_spend = self.solver.Value(self.model.max_mana_spend)  # BAKERT this is also derivable from max fo constriants.turn so idk why we model it?
        self.pain = self.solver.Value(self.model.pain)  # BAKERT can also access vars here not use get … this is all a bit messy needs some thought
        self.objective = self.solver.Value(self.model.objective)
        # BAKERT only if the solve value > 0
        self.required = {k: self.solver.Value(v) for k, v in self.model.required.items() if self.solver.Value(v) > 0}
        self.sources = {k: self.solver.Value(v) for k, v in self.model.sources.items() if self.solver.Value(v) > 0}
        # BAKERT this is a type error because var could be an int. That won't happen because we only use int for 0 but maybe handle or maybe always return an IntVar of 0 not 0?
        self.providing = {k: [f"{self.solver.Value(var)} {var.name}" for var in v if self.solver.Value(var) > 0] for k, v in self.model.providing.items()}

    @property
    def num_lands(self) -> int:
        return sum(self.lands.values())

    @property
    def total_lands(self) -> int:
        return self.num_lands  # BAKERT only one of these two please

    def __repr__(self) -> str:
        optimality = "not " if self.status != cp_model.OPTIMAL else ""  # BAKERT should Solution know about cp_model?
        s = f"Solution ({optimality}optimal)\n\n"
        s += f"{self.num_lands} Lands (min {self.min_lands})\n\n"
        s += f"Mana spend: {self.mana_spend}/{self.max_mana_spend}\n\n"
        for land in sorted(self.lands):
            s += f"{self.lands[land]} {land}\n"
        s += "\n"
        for constraint in sorted(self.constraints):
            s += f"Constraint {constraint}\n"
            # BAKERT we end up with "4 Sunken Ruins 2" where we should have either "4 Sunken Ruins" or "4 Sunken Ruins T2"
            # BAKERT should constraint provide .resources() that includes UNTAPPED instead of using color_combinations and tacking it on?
            resources = sorted(constraint.color_combinations()) + [UNTAPPED]  # BAKERT literal constant
            for resource in resources:
                s += f"T{constraint.turn} {resource} "
                s += f"required={self.required[(constraint.turn, resource)]} "
                s += f"sources={self.sources[(constraint.turn, resource)]} "
                s += f"providing={", ".join(self.providing[(constraint.turn, resource)])}\n"
            s += "\n"
        s += f"\n{self.objective}\n"
        return s

    def __str__(self) -> str:
        return self.__repr__()


def card(spec: str, turn: int | None = None) -> Constraint:
    colors: list[Color] = []
    generic = 0
    for i in range(len(spec) - 1, -1, -1):
        c = spec[i]
        if c.isnumeric():
            generic = int(spec[0 : i + 1])
            break
        colors.insert(0, next(color for color in all_colors if color.code == c))
    parts = ([generic] if generic else []) + colors
    return Constraint(ManaCost(*parts), turn if turn else generic + len(colors))


# BAKERT need some way to say "the manabase must include 4 Shelldock Isle"
def solve(constraints: frozenset[Constraint], lands: frozenset[Land] | None = None) -> Solution | None:
    # T2 RR completely counterfeits T2 R so there's no point in frank returning R=13, but you still need R in BR or BBR
    if not lands:
        lands = all_lands
    model = define_model(constraints, lands)
    solver = cp_model.CpSolver()
    status = solver.solve(model.model)  # BAKERT would be nice to not stutter here
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        return None
    return Solution(constraints, status, model, solver)


# BAKERT this function is too large, break it up
def define_model(constraints: frozenset[Constraint], lands: frozenset[Land]) -> Model:
    possible_lands = viable_lands(find_colors(constraints), lands)
    model = Model(possible_lands)

    # BAKERT really need to type alias ColorCombination if it's not possible to annotate with type
    # BAKERT can we just make color_vars as we need them now they are not passed in to add_to_model
    # BAKERT add_to_model is not the right name unless we generalize it
    color_vars: dict[Constraint, Contributions] = {}
    sources: dict[Constraint, dict[ColorCombination, list[IntVar]]] = {}
    # BAKERT now unused? untapped_sources: dict[Constraint, ] = {}
    for constraint in constraints:
        color_combinations = constraint.color_combinations()
        for color_combination in color_combinations:
            if constraint not in color_vars:
                color_vars[constraint] = {}
                sources[constraint] = {}
            if color_combination not in color_vars[constraint]:
                color_vars[constraint][color_combination] = model.new_sources(constraint.turn, color_combination)
                sources[constraint][color_combination] = []
        # BAKERT now unused? untapped_sources[constraint] = []

    # BAKERT treating each constraint as independent isn't quite right. If you sac a land for RR to play something you can't sac it for UU to play something else, so it's not totally independent
    # So we need to ask lands "add_to_model" passing in all constraints?

    for constraint in constraints:
        # BAKERT this is not quite right because of Ancient Tomb and so on
        if constraint.turn == constraint.required.mana_value:
            required_untapped = need_untapped(constraint.turn)
        else:
            required_untapped = 0
        for land in model.lands:
            # BAKERT we want to be able to think about untappedness here, too. You can only meet a requirement that's of mana value N if you're producing N mana, obviously
            # we want to check that there are enough lands that CAN be part of this cost and ALSO come into play untapped on constraint.turn
            # This is not relevant if constraint.turn > constraint.required.mana_value
            # BAKERT if you ask about U on turn 2 as part of UU and part of UW and part of 1U we want to be able to give different answers without them all being added together
            contributions = land.add_to_model(model, constraint)
            for color_combination, contribution in contributions.items():
                sources[constraint][color_combination].append(contribution)
        # BAKERT frank should return the powerset-y thing not what it currently returns. or we can do that here if necessary
        requirements = frank(constraint)
        for color_combination, required in requirements.items():
            # BAKERT
            r = model.new_required(constraint.turn, color_combination)
            model.add(r == required)
            model.add(color_vars[constraint][color_combination] >= required)  # BAKERT looks like color_vars IS used

        if required_untapped:
            # BAKERT this whole section isn't really how we do things now, push the color checking/generic part into the Land classes?
            generic_ok = len(constraint.required.pips) > len(constraint.required.colored_pips)
            admissible_untapped = {}
            for land, var in model.lands.items():
                makes_one_of_the_colors = any(land.can_produce_any(colors) for colors in frank(constraint))
                if generic_ok or makes_one_of_the_colors:
                    admissible_untapped[land] = var
            # BAKERT "save" the amount of untapped lands at each constraint-critical turn and use that in the overall score
            # BAKERT is the third arg to untapped_rules land_vars, or admissible_untapped? I think land_vars?
            lands_that_are_untapped_this_turn = [land.untapped_rules(model, constraint.turn) for land in admissible_untapped]
            model.new_providing(constraint.turn, UNTAPPED, lands_that_are_untapped_this_turn)
            untapped_this_turn = sum(lands_that_are_untapped_this_turn)
            # BAKERT this is always equal to the required but surely it should exceed the required when we have more untapped lands than that? Or am I just lost in the sauce?
            untapped_sources = model.new_sources(constraint.turn, UNTAPPED)
            model.add(untapped_sources == untapped_this_turn)
            untapped = model.new_required(constraint.turn, UNTAPPED)
            # BAKERT untapped = model.new_int_var(0, MAX_DECK_SIZE, (constraint.turn, UNTAPPED)) # BAKERT maybe make all these magic strings into enum constants
            # BAKERT somewhere in all this we've stopped storing ALL vars and so we can't inspect the whole mess
            model.add(untapped == untapped_this_turn)
            model.add(untapped_this_turn >= required_untapped)

            # BAKERT can we just use the old implementation of untapped or do we need to modernize to per-constraint land?
            # untapped_sources[constraint].append(land.untapped_rules(model, constraint.turn, land_vars))  # BAKERT do we ever use color_vars?
            # model.add(sum(untapped_sources[constraint]) >= required_untapped)

    for constraint, contributions_by_color in sources.items():
        for color_combination, contribs in contributions_by_color.items():
            # BAKERT not a great name
            # BAKERT this is where we add sources but we don't require anything of sources. instead we require of has. but we don't need has we can just require of sources.
            sources_of_this = model.new_sources(constraint.turn, color_combination)  # BAKERT this overwrites an existing var and is pointless (in color_vars)
            model.add(sources_of_this == sum(contribs))  # BAKERT is there a better or more standard way of providing these vars that also do work?
            model.new_providing(constraint.turn, color_combination, contribs)  # BAKERT probably a better way to do this
            model.add(color_vars[constraint][color_combination] == sum(contribs))

    min_lands = model.min_lands  # BAKERT this is an ugly construction
    model.add(min_lands == max(num_lands_required(constraint) for constraint in constraints))
    total_lands = model.total_lands
    model.add(total_lands == sum(model.lands.values()))
    model.add(total_lands >= min_lands)

    # BAKERT I think this is really broken if, say, our only 1-2 drops are Priest of Fell Rites and Tainted Indulgence
    mana_spend = model.mana_spend
    max_mana_spend = model.max_mana_spend
    max_mana_spend_per_turn, mana_spend_per_turn = [], []
    max_turn = max(constraint.turn for constraint in constraints) + 1
    for turn in range(1, max_turn):
        # BAKERT the other place where we do this kind of thing we use admissible_untapped not land_vars … is this a bug? Does it matter?
        untapped_this_turn = sum(land.untapped_rules(model, turn) for land in model.lands)
        # BAKERT this isn't quite right it's kind of 1, turn (independently executed) and it's kind of turn, turn (if you spent every turn so far)
        needed = num_lands(turn, turn)
        enough_untapped = model.new_bool_var((turn, "can spend mana"))  # BAKERT get consistent about underscores or whatever
        model.add(untapped_this_turn >= needed).OnlyEnforceIf(enough_untapped)
        model.add(untapped_this_turn < needed).OnlyEnforceIf(enough_untapped.Not())
        max_mana_spend_this_turn = model.new_int_var(turn, turn, (turn, "max_mana_spend"))  # BAKERT turn being just an int makes this "risky" … maybe key formation is a func somewhere? Maybe Model *does* know about land, required, etc. Or another layer on top of Model
        model.add(max_mana_spend_this_turn == turn)
        max_mana_spend_per_turn.append(max_mana_spend_this_turn)
        mana_spend_this_turn = model.new_int_var(turn - 1, turn, (turn, "mana_spend"))
        model.add(mana_spend_this_turn == turn).OnlyEnforceIf(enough_untapped)
        model.add(mana_spend_this_turn == turn - 1).OnlyEnforceIf(enough_untapped.Not())
        mana_spend_per_turn.append(mana_spend_this_turn)
    model.add(max_mana_spend == sum(max_mana_spend_per_turn))
    model.add(mana_spend == sum(mana_spend_per_turn))

    # BAKERT this should maybe be modeled as pain spent in first N turns rather than just how many painlands
    # BAKERT t1 combo don't care about pain, t20 control cares a lot, I think?
    # BAKERT should this be pushed into add_to_model? Should everything? Or rename it colored_sources?
    pain = model.pain
    model.add(pain == sum(model.lands[land] for land in model.lands if land.painful))

    # Give a little credit for extra sources. if you can double spell sometimes more your manabase is better
    all_colored_sources = []
    # BAKERT this should be points for excess not just points
    # BAKERT but this should give more weight to B if you have 9 B spells and one W spell
    # BAKERT and earlier matters somehow?
    deck_colors = {color for color in [constraint.color_combinations for constraint in constraints]}
    for color in deck_colors:
        contributing_lands = sum([var for land, var in model.lands.items() if color in land.produces])
        colored_sources = model.new_int_var(0, MAX_DECK_SIZE, (color, "colored_sources"))
        model.add(colored_sources == contributing_lands)
        all_colored_sources.append(contributing_lands)
    total_colored_sources = model.new_int_var(0, MAX_DECK_SIZE, ("total_colored_sources",))
    model.add(total_colored_sources == sum(all_colored_sources))

    # BAKERT if a deck is playing 5+ drops it cares less about fitting in 24 lands than a deck curving out to 4
    # mana_spend = 0 to 15(ish)
    # lands = 14 to 24(ish)
    # colored_sources = 14 to 120ish
    # pain = 0 to 24 (or calculate it differently)
    # BAKERT make vars for each part of the score and display them in solution
    # BAKERT type: ignore here is bad
    objective = model.objective
    # BAKERT normalize this over possible score
    # BAKERT max_objective = max_mana_spend + 0 - 0 + len(deck_colors) * 60
    model.add(objective == 1000 + mana_spend * 6 - total_lands * 10 - pain * 2 + total_colored_sources)
    model.maximize(objective)  # type: ignore

    return model


# RRB => R, B, RR, RB, RRB
# GGGG => G, GG, GGG, GGGG
def find_color_combinations(colored_pips: tuple[Color, ...]) -> frozenset[ColorCombination]:
    # BAKERT we don't need multiset? Although mana cost could be a multiset
    return frozenset(ColorCombination(item) for item in powerset(colored_pips) if item)


def find_colors(constraints: frozenset[Constraint]) -> set[Color]:
    colors = set()
    for constraint in constraints:
        for pip in constraint.required.colored_pips:
            colors.add(pip)
    return colors


# BAKERT should colors be a frozenset here too?
def viable_lands(colors: set[Color], lands: frozenset[Land]) -> frozenset[Land]:
    possible_lands = set()
    for land in lands:
        # BAKERT some simplifying pd-specific assumptions here about what lands we might be interested in
        if len(colors) <= 2 and len([c for c in land.produces if c != C]) > 2:
            continue
        if len(colors.intersection(land.produces)) >= 2 or (colors.intersection(land.produces) and isinstance(land, Basic)):
            possible_lands.add(land)
    return frozenset(possible_lands)


# BAKERT or is it better to use this? https://www.channelfireball.com/article/How-Many-Lands-Do-You-Need-in-Your-Deck-An-Updated-Analysis/cd1c1a24-d439-4a8e-b369-b936edb0b38a/
# 19.59 + 1.90 * average mana value – 0.28 * number of cheap card draw or mana ramp spells + 0.27 * companion count
def num_lands_required(constraint: Constraint) -> int:  # BAKERT wait isn't this num_colored_sources_required?
    return num_lands(constraint.required.mana_value, constraint.turn)


def need_untapped(turn: int) -> int:
    try:
        return frank(Constraint(ManaCost(C), turn))[ColorCombination({C})]
    except UnsatisfiableConstraint:
        # We don't know how many untapped lands you need beyond turn 6 so supply an overestimate
        return frank(Constraint(ManaCost(C), 6))[ColorCombination({C})]


class UnsatisfiableConstraint(Exception):
    pass


# https://www.channelfireball.com/article/how-many-sources-do-you-need-to-consistently-cast-your-spells-a-2022-update/dc23a7d2-0a16-4c0b-ad36-586fcca03ad8/
# BAKERT basically every set should be a frozenset
# BAKERT I made frank a lot more unpleasant by having it return {frozenset({R}): 18, frozenset({B}): 12, frozenset({R, B}): 23} instead of {R: 18, B: 12} but it doesn't seem to have had the effect I want on the output
# BAKERT should be a frozenmultiset not a set in return value
def frank(constraint: Constraint, deck_size: int = 60) -> dict[ColorCombination, int]:  # BAKERT how to mypy that the ColorCombinations must contain only Colors?
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
    color_set = constraint.color_combinations()  # BAKERT we seem to do this in a few places … do it inside Constraint or something?
    results = {}
    for colors in color_set:
        num_pips = len(colors)  # BAKERT sum(1 for c in constraint.required.colored_pips if c in colors)
        req = table.get((num_pips, constraint.turn), {}).get(deck_size)
        if not req:
            raise UnsatisfiableConstraint(f"{num_pips} {constraint.turn} {deck_size}")
        results[colors] = req
    return results


def num_lands(mana_value: int, turn: int) -> int:
    try:
        return frank(Constraint(turn=turn, required=ManaCost(*[W] * mana_value)))[ColorCombination([W] * mana_value)]
    except UnsatisfiableConstraint:
        # We are at mana value 5 or beyond, return an underestimate, but better than nothing
        return frank(Constraint(turn=4, required=ManaCost(*[W] * 4)))[ColorCombination([W] * 4)]


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

KikiOnSix = card("2RRR", 6)

jeskai_twin_base = frozenset([BurstLightningOnTurnTwo, MemoryLapse, Pestermite, RestorationAngel])
jeskai_twin = frozenset(jeskai_twin_base | {KikiJikiMirrorBreaker})
jeskai_twin_with_the_ravens_warning = frozenset(jeskai_twin | {DeputyOfDetention})
jeskai_twin_but_dont_rush_kiki = frozenset(jeskai_twin_base | {KikiOnSix})

CracklingDrake = card("UURR")

GloryBringer = card("3RR")
AcademyLoremaster = card("UU")

KikiOnSix = card("2RRR", 6)

izzet_twin = frozenset([BurstLightningOnTurnTwo, MemoryLapse, Pestermite, AcademyLoremaster, KikiOnSix])

BenevolentBodyguard = Constraint(ManaCost(W), 1)
MeddlingMage = Constraint(ManaCost(U, W), 2)
SamuraiOfThePaleCurtain = Constraint(ManaCost(W, W), 2)

azorius_taxes = frozenset([BenevolentBodyguard, MeddlingMage, SamuraiOfThePaleCurtain, DeputyOfDetention])

SettleTheWreckage = Constraint(ManaCost(2, W, W), 4)
VenserShaperSavant = card("2UU")

azorius_taxes_postboard = frozenset(azorius_taxes | {SettleTheWreckage})

mono_w_bodyguards = frozenset([BenevolentBodyguard])
white_weenie = frozenset([BenevolentBodyguard, SamuraiOfThePaleCurtain])
meddlers = frozenset([MeddlingMage])

InvasionOfAlara = Constraint(ManaCost(W, U, B, R, G), 5)
invasion_of_alara = frozenset([InvasionOfAlara])

Duress = card("B")
Abrade = card("1R")
DigThroughTime = card("UU", 5)
WrathOfGod = card("2WW", 4)

popular = frozenset([MemoryLapse, Abrade, DigThroughTime, WrathOfGod])

BaskingRootwalla = card("G")
PutridImp = card("B")
LotlethTroll = card("BG")
LotlethTrollWithRegen = card("BBG")

golgari_madness = frozenset([PutridImp, LotlethTroll])

GrimLavamancer = card("R")
Pteramander = card("U")
LogicKnot = card("1UU")

gfabsish = frozenset([GrimLavamancer, Pteramander, VenserShaperSavant])

Assault = card("R", 2)
LagoonBreach = card("1U")
MadcapExperiment = card("3R")
Away = card("2B")
ChainOfPlasma = card("1R")

my_invasion_of_alara = frozenset([Assault, LagoonBreach, MadcapExperiment, Away, InvasionOfAlara, ChainOfPlasma])

GiantKiller = card("W")
KnightOfTheWhiteOrchid = card("WW")
SunTitan = card("4WW")

emeria = frozenset([GiantKiller, KnightOfTheWhiteOrchid, SunTitan])

PriestOfFellRites = card("WB")
HaakonStromgaldScourge = card("1BB", 5)
MagisterOfWorth = card("4WB")
OptOnTurn2 = card("U", 2)
SearchForAzcanta = card("1U")
CouncilsJudgment = card("1WW", 4)
EsperCharm = card("WUB")
ForbidOnTurnFour = card("1UU", 4)
WrathOfGod = card("2WW")

gifts = frozenset([PriestOfFellRites, HaakonStromgaldScourge, MagisterOfWorth, OptOnTurn2, SearchForAzcanta, CouncilsJudgment, EsperCharm, ForbidOnTurnFour, WrathOfGod])

actual_twin = frozenset([GrimLavamancer, Pteramander, KikiJikiMirrorBreaker, DigThroughTime])

# Crypt of Agadeem possibly beyond simulation :)
LamplightPhoenix = card("1RR")
BigCyclingTurn = card("BBB")
BringerOfTheLastGift = card("6BB")
StarvingRevenant = card("2BB")
ArchfiendOfIfnir = card("3BB")

midnight_phoenix = frozenset([LamplightPhoenix, BigCyclingTurn, StarvingRevenant, ArchfiendOfIfnir])

Cremate = card("B")
GlimpseTheUnthinkable = card("UB")

mill = frozenset([Cremate, GlimpseTheUnthinkable, DigThroughTime])

HomeForDinner = card("1W")
GeologicalAppraiser = card("2RR")
SuspendGlimpseOnTwo = card("RR")
SuspendGlimpseOnThree = card("RR", 3)
CavalierOfDawn = card("2WWW")
ChancellorOfTheForge = card("4RRR")
EtalisFavor = card("2R")

glimpse = frozenset([HomeForDinner, GeologicalAppraiser, EtalisFavor])

SeismicAssault = card("RRR")
SwansOfBrynArgoll = card("2UU")

seismic_swans = frozenset([SeismicAssault, SwansOfBrynArgoll])

NecroticOoze = card("2BB")
GiftsUngiven = card("3U")
TaintedIndulgence = card("UB")
BuriedAlive = card("2B")

ooze = frozenset({NecroticOoze, PriestOfFellRites, TaintedIndulgence, GiftsUngiven, BuriedAlive})

BloodsoakedChampion = card("B")
UnluckyWitness = card("R")
DreadhordeButcher = card("BR")
LightningSkelemental = card("BRR")

skelemental_sac = frozenset([BloodsoakedChampion, UnluckyWitness, DreadhordeButcher, LightningSkelemental])

Korlash = card("2BB")
Lashwrithe = card("4")
PlagueStinger = card("1B")

mono_b_infect = [Korlash, Lashwrithe, PlagueStinger]

ArchiveDragon = card("4UU")
NorinTheWary = card("R")

our_deck = frozenset([NorinTheWary, ArchiveDragon])

CenoteScout = card("G")
CenoteScoutOnTwo = card("G", 2)
MasterOfThePearlTrident = card("UU")
KumenaTyrantOfOrazca = card("1GU")

ug_merfolk = frozenset([CenoteScoutOnTwo, MasterOfThePearlTrident, KumenaTyrantOfOrazca])

splash_gifts_ooze = frozenset([NecroticOoze, PriestOfFellRites, GiftsUngiven, BuriedAlive])

wb_ooze = frozenset([NecroticOoze, PriestOfFellRites])

KarmicGuide = card("3WW")
ConspiracyTheorist = card("1R")
# BAKERT why does this add Restless Vents and not Vivid Crag?
ooze_kiki = frozenset([ConspiracyTheorist, KarmicGuide, KikiJikiMirrorBreaker, PriestOfFellRites, RestorationAngel, BuriedAlive, BurstLightningOnTurnTwo])


# BAKERT make these "real" unit tests
def test_remembering_model_collision() -> None:
    model = RememberingModel()
    model.new_int_var(0, 1, ("test",))
    model.new_int_var(0, 1, ("test", "other"))
    found = False
    try:
        model.new_int_var(0, 2, ("test",))
    except KeyCollision:
        found = True
    assert found


def test_viable_lands() -> None:
    lands = frozenset({Plains, Island, Swamp, CelestialColonnade, StirringWildwood, CreepingTarPit})
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
    model = Model(all_lands)
    constraint = card("U")
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == 0
    constraint = card("2U")
    contributions = PrairieStream.add_to_model(model, constraint)
    assert contributions[ColorCombination({U})] == model.lands[PrairieStream]


def test_add_to_model() -> None:
    model = Model(all_lands)
    constraint = card("WU")
    plains, island, mystic_gate = model.lands[Plains], model.lands[Island], model.lands[MysticGate]
    contributions = MysticGate.add_to_model(model, constraint)
    assert contributions[ColorCombination([W])] == mystic_gate
    assert contributions[ColorCombination([U])] == mystic_gate
    multicolor_contribs_s = str(contributions[ColorCombination([W, U])])
    assert "Mystic" in multicolor_contribs_s
    assert "Sunken" not in multicolor_contribs_s
    # BAKERT (W, U) means W || U not W && U, Filter needs to learn that
    # BAKERT can test a lot more here, and should


def test_sort_lands() -> None:
    lands = [GlacialFortress, FireLitThicket, SunkenRuins, AdarkarWastes]
    assert sorted(lands) == [AdarkarWastes, GlacialFortress, SunkenRuins, FireLitThicket]


def test_solve() -> None:
    solution = solve(mono_w_bodyguards, frozenset({Plains, Island, MysticGate}))
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[Plains] == 14
    assert solution.lands.get(Island) is solution.lands.get(MysticGate) is None

    solution = solve(azorius_taxes)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.num_lands == 23
    assert solution.lands[PortTown] == 4
    assert solution.lands[Plains] == 10
    # BAKERT when we're more sure about what we want here, assert more. In particular 4 Mystic Gate?

    boros_burn = frozenset([card("W"), card("R"), card("WR")])
    solution = solve(boros_burn)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[BattlefieldForge] == 4

    counter_weenie = frozenset([card("WW"), card("UU")])
    solution = solve(counter_weenie)
    assert solution
    assert solution.status == cp_model.OPTIMAL
    assert solution.lands[MysticGate] == 4

    basics_and_tango = frozenset({Plains, Island, PrairieStream})
    light = frozenset({card("1W"), card("1U")})
    solution = solve(light, basics_and_tango)
    assert solution
    assert solution.lands[PrairieStream] == 4
    intense = frozenset({card("W"), card("U"), card("WW")})
    solution = solve(intense, basics_and_tango)
    assert solution
    assert not solution.lands.get(PrairieStream)

    # BAKERT figure this out
    necrotic_ooze = frozenset([card("B", 2), card("UB"), card("WB"), card("2B"), card("3U"), card("2BB")])
    solution = solve(necrotic_ooze)
    assert solution
    print(solution)
    assert solution.status == cp_model.OPTIMAL
    assert not solution.lands.get(MysticGate)
    assert not solution.lands.get(CrumblingNecropolis)
    # BAKERT assert solution.lands[RiverOfTears] == 4


def test() -> None:
    test_remembering_model_collision()
    test_viable_lands()
    test_str_repr()
    test_basic_land_types()
    test_frank()
    test_filter()
    test_tango()
    test_add_to_model()
    test_sort_lands()
    test_solve()


# BAKERT you should never choose Crumbling Necropolis over a check or a snarl in UR (or UB or RB)
# BAKERT in general you should be able to get partial credit for a check or a snarl even if not hitting the numbers

# BAKERT
# Phyrexian mana
# Hybrid mana
# Snow mana and snow lands and snow-covered basics
# Yorion
# Commander
# Limited

# BAKERT test Absorb, Cryptic Command and other intense costs with Filters that help

# BAKERT the untapped rules should possibly be per-constraint, although it'd be nice to know through the whole set of constraints
# Can we integrate untapped rules into add_to_model?

# BAKERT add_to_model of a check/snarl doesn't do any untapped checking. is that because the untapped checking will make that ok separately, or is it a bug?

# BAKERT notes on how many filters to play https://www.channelfireball.com/article/Understanding-and-Selecting-Lands-for-Modern-Deep-Dive/ebd94a5a-6525-4f34-8931-1803f3a09559/
# Is our model suitably filter-averse? How do we account for the fact that you might want to Duress on your turn and then Mana Leak on their turn but all you have are 2 Sunken Ruins and a Swamp. Filters are being oversold currently.

# BAKERT in several places we make the assumption that a land cannot make more than one mana. The filterlands in particular think you will never make more than 1 other mana on turn 2.

# BAKERT Solution could be a lot nicer and be able to spit out the manabase, etc. Solution.lands could be its own class with a __str__/__repr__

# BAKERT
# Mana costs are tuples because they (kinda) have an order
# Color combinations are FrozenMultisets and do not have an order
# But in a sense these are the same thing - {1}{B}{R} being pretty similar to {B}{R} so maybe they should both use the same representation?
# perhaps best of all is if mana costs are frozen multisets but something knows how to present them in the right order?

# BAKERT Now that multiset supports mypy I should be able to say x: FrozenMultiset[Color] but this causes a runtime error

if len(sys.argv) >= 2 and (sys.argv[1] == "--test" or sys.argv[1] == "-t"):
    test()
else:
    print(solve(ooze))
