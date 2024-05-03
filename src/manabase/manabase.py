from dataclasses import dataclass, field, fields
from enum import Enum
from functools import total_ordering
from typing import Any, Iterable, overload, override

from more_itertools import powerset
from multiset import FrozenMultiset
from ortools.sat.python import cp_model

from .remembering_model import RememberingModel


@dataclass
class Weights:
    # A score from 0-21 for how much untapped mana the deck has available on the turns it cares about. 21 = always untapped lands, 0 = always tapped lands
    normalized_mana_spend: int
    # How many lands the deck plays BAKERT could be number above min lands instead?
    total_lands: int
    # How many lands the deck plays that require a life payment to make a color. BAKERT this could be modelled way better.
    pain: int
    # Num lands x num colors made by those lands. BAKERT is this a measure of anything we care about?
    total_colored_sources: int


DEFAULT_WEIGHTS = Weights(normalized_mana_spend=5, total_lands=-10, pain=-1, total_colored_sources=0)

# BAKERT can we avoid the whole normalized_mana_spend thing by just putting the number we actually want in the module in the first place somehow?


# BAKERT this is just floating around
def score(values: dict[str, int], weights: Weights) -> int:
    return sum(values[k.name] * getattr(weights, k.name) for k in fields(weights))


class Aspect(Enum):
    UNTAPPED = "untapped"

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return self.value


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


class Turn(int):
    @property
    def min_mana_spend(self) -> int:
        return triangle(self - 1)

    @property
    def max_mana_spend(self) -> int:
        # This is Ancient Tomb erasure, but the maximum amount of mana you could have spent by the end of this turn
        return triangle(self)

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return "T" + super().__repr__()


@dataclass(eq=True, frozen=True, order=True)
class Constraint:
    required: ManaCost
    turn: Turn = Turn(-1)

    # Do we want R when we're already returning RR? Or should strict subsets be removed??
    # RRB => R, B, RR, RB, RRB
    # GGGG => G, GG, GGG, GGGG
    # BAKERT move this to deck to avoid redundancy or move a (turn, resource) version to deck
    def color_combinations(self) -> frozenset[ColorCombination]:
        return frozenset(ColorCombination(item) for item in powerset(self.required.colored_pips) if item)

    def __post_init__(self) -> None:
        if self.turn == -1:
            object.__setattr__(self, "turn", Turn(self.required.mana_value))

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.turn} {self.required}"


@dataclass(eq=True, frozen=True)
class Deck:
    constraints: frozenset[Constraint]
    size: int

    @property
    def fundamental_turn(self) -> Turn:
        return max(constraint.turn for constraint in self.constraints)

    @property
    def colors(self) -> frozenset[Color]:
        return frozenset(pip for constraint in self.constraints for pip in constraint.required.colored_pips)


IntVar = cp_model.IntVar | int
Contributions = dict[ColorCombination, IntVar]
Resource = ColorCombination | Aspect
ResourceVars = dict[Resource, list[IntVar]]
ConstraintVars = dict[Constraint, ResourceVars]


# BAKERT this belongs somewhere, presumably. On Turn??
def triangle(n: int) -> int:
    return n * (n + 1) // 2  # 1 + 2 + 3 …


@overload
def normalized_mana_spend(turn: Turn, mana_spend: int) -> int: ...


@overload
def normalized_mana_spend(turn: Turn, mana_spend: cp_model.IntVar) -> cp_model.LinearExprT: ...


# BAKERT
# Even this is not really sufficient because you don't care about t1 if you don't have any one drops but our model is breaking its neck to give you t1
# Maybe we just give you automatic point for each turn where you don't have a constraint.turn?
# So a deck with only one drops would care 0-21 for an untapped land on turn 1
# But a deck with no ones or two could only care about enough untapped lands for t3
def normalized_mana_spend(turn: Turn, mana_spend: IntVar) -> Any:  # BAKERT type
    if turn > 6:  # BAKERT magic six
        raise Exception("BAKERT")
    # BAKERT I'd like to do bounds checking on mana_spend but if it's an IntVar that isn't possible(??)
    min_mana_spend = triangle(turn - 1)
    max_mana_spend = triangle(turn)
    width = max_mana_spend - min_mana_spend
    points_per_mana_above_min = triangle(6) // width  # BAKERT what effect does this have?
    mana_spend_above_min = mana_spend - min_mana_spend
    return mana_spend_above_min * points_per_mana_above_min


class Model(RememberingModel):
    def __init__(self, deck: Deck, possible_lands: frozenset["Land"], weights: Weights, forced_lands: dict["Land", int] | None = None, debug: bool = False):
        super().__init__(debug)
        self.deck = deck
        self.lands = {land: self.new_int_var(0, land.max if land.max else deck.size, (land,)) for land in possible_lands}
        self.weights = weights
        if not forced_lands:
            forced_lands = {}
        self.min_lands = self.new_int_var(0, self.deck.size, ("min_lands",))
        self.mana_spend = self.new_int_var(0, self.deck.fundamental_turn.max_mana_spend, ("mana_spend",))
        self.normalized_mana_spend = self.new_int_var(0, triangle(Turn(6)), ("normalized_mana_spend",))  # BAKERT another magic number 6
        self.total_lands = self.new_int_var(0, self.deck.size, ("total_lands",))
        self.pain = self.new_int_var(0, self.deck.size, ("pain",))
        self.total_colored_sources = self.new_int_var(0, self.deck.size * len(self.deck.colors), ("total_colored_sources",))
        self.objective = self.new_int_var(-1000, 1000, ("objective",))
        self.required: dict[tuple[Turn, Resource], cp_model.IntVar] = {}
        self.sources: dict[tuple[Turn, Resource], cp_model.IntVar] = {}
        self.providing: dict[tuple[Turn, Resource], list[IntVar]] = {}
        # forced_lands is so much like "at least 4 shelldock isle" but just slightly different because of the total_lands ==
        for land, n in forced_lands.items():
            self.add(self.lands[land] == n)
        if forced_lands:
            self.add(self.total_lands == sum(forced_lands.values()))

    def new_required(self, turn: Turn, resource: Resource) -> cp_model.IntVar:
        self.required[(turn, resource)] = self.new_int_var(0, self.deck.size, (turn, resource, "required"))
        return self.required[(turn, resource)]

    def new_sources(self, turn: Turn, resource: Resource) -> cp_model.IntVar:
        self.sources[(turn, resource)] = self.new_int_var(0, self.deck.size, (turn, resource, "sources"))
        return self.sources[(turn, resource)]

    # BAKERT providing is kind of weird … why is it even necessary? it's possible we want to change the behavior of `add` (and `NewIntVar`/`NewBoolVar`??) to store basically everything rather the explicitly calling remember
    def new_providing(self, turn: Turn, resource: Resource, sources: list[IntVar]) -> None:
        self.providing[(turn, resource)] = sources

    def objective_function(self) -> cp_model.LinearExprT:
        return sum(getattr(self, k.name) * getattr(self.weights, k.name) for k in fields(self.weights))


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
    def max(self) -> int | None:
        # Some cards break this rule and have specific rules text to say so, including Seven Dwarves as well as unlimited
        return None if self.is_basic else 4

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

    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
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


Manabase = dict[Land, int]


@dataclass(eq=True, frozen=True, repr=False)
class Nonbasic(Land):
    @override
    @property
    def max(self) -> int:
        return 4


@dataclass(eq=True, frozen=True, repr=False)
class Basic(Land):
    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
        return model.lands[self]

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if self.can_produce_any(color_combination):
                contributions[color_combination] = model.lands[self]
            else:
                contributions[color_combination] = 0
        return contributions


class Conditional(Nonbasic):
    def untapped_if(self, model: Model, turn: Turn, needed: int, enablers: cp_model.LinearExprT, land_var: cp_model.IntVar) -> cp_model.IntVar:
        untapped_var = model.new_bool_var((self, turn, Aspect.UNTAPPED))
        model.add(enablers >= needed).OnlyEnforceIf(untapped_var)  # type: ignore
        model.add(enablers < needed).OnlyEnforceIf(untapped_var.Not())
        makes_mana_var = model.new_int_var(0, 4, (self, turn))
        model.add(makes_mana_var == land_var).OnlyEnforceIf(untapped_var)
        model.add(makes_mana_var == 0).OnlyEnforceIf(untapped_var.Not())
        return makes_mana_var


@dataclass(eq=True, frozen=True, repr=False)
class Tapland(Nonbasic):
    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
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

    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
        if self.zone == Zone.BATTLEFIELD and turn == 1:
            return 0
        enabling_lands = {var for land, var in model.lands.items() if land.has_basic_land_types(self.basic_land_types_needed)}
        # This crudely models the difficulty of playing a Snarl untapped after t1 but overestimates that difficulty by assuming you always play an enabling land each turn
        needed = need_untapped(turn, model.deck.size) if self.zone == Zone.BATTLEFIELD else num_lands(turn, turn, model.deck.size)
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
    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
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
        needed = need_untapped(turn, model.deck.size)
        enablers = sum(enabling_lands)
        return self.untapped_if(model, turn, needed, enablers, model.lands[self])  # BAKERt remove this param in favor of reading it from model

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        m, n, _ = self.produces
        land_var = model.lands[self]
        contributions: Contributions = {}

        # Eject early saying we can only make colorless mana if it's turn 1, or we don't make any of the colors requested.
        if constraint.turn == 1 or not any(self.can_produce_any(c) for c in constraint.color_combinations()):
            return {color_combination: land_var if C in color_combination else 0 for color_combination in constraint.color_combinations()}

        c_sources = model.new_int_var(0, self.max, (self, constraint))
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
        required = need_untapped(constraint.turn, model.deck.size)  # BAKERT need_untapped now a bad name for this func
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
class Pain(Nonbasic):
    painful: bool = True

    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
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
# BAKERT we must at least explain that it's worse than an Island in a non-B deck and worse than a Swamp in a non-U deck somehow
@dataclass(eq=True, frozen=True, repr=False)
class RiverOfTearsLand(Nonbasic):
    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
        return model.lands[self]

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        contributions: Contributions = {}
        for color_combination in constraint.color_combinations():
            if U in color_combination or B in color_combination:
                contributions[color_combination] = model.lands[self]
        return contributions


@dataclass(eq=True, frozen=True, repr=False)
class Tango(Conditional):
    def untapped_rules(self, model: Model, turn: Turn) -> IntVar:
        if turn <= 2:
            return 0
        needed = num_lands(2, Turn(turn - 1), model.deck.size)
        enablers = sum(var for land, var in model.lands.items() if land.is_basic)
        return self.untapped_if(model, turn, needed, enablers, model.lands[self])

    def add_to_model(self, model: Model, constraint: Constraint) -> Contributions:
        # BAKERT add_to_model and untapped_rules kind of counterfeit one another, can we combine them?
        if constraint.turn == 1:
            return {color_combination: 0 for color_combination in constraint.color_combinations()}
        return {color_combination: model.lands[self] if self.can_produce_any(color_combination) else 0 for color_combination in constraint.color_combinations()}


class IntValueException(Exception):
    pass


@total_ordering
class Solution:  # BAKERT it would be nice to put the amount each thing is contributing to score alongside the thing Total lands: 23 (-230) or even normalized for that one aspect … Total lands: 23 (1.0)
    def __init__(self, status: int, model: Model, solver: cp_model.CpSolver) -> None:
        self.status = status
        self.model = model
        self.solver = solver
        self.lands = {land: self.solver.Value(var) for land, var in self.model.lands.items() if self.solver.Value(var) > 0}
        self.min_lands = self.solver.Value(self.model.min_lands)
        self.mana_spend = self.solver.Value(self.model.mana_spend)
        self.normalized_mana_spend = self.solver.Value(self.model.normalized_mana_spend)
        self.pain = self.solver.Value(self.model.pain)
        self.total_colored_sources = self.solver.Value(self.model.total_colored_sources)
        self.objective = int(self.solver.ObjectiveValue())
        self.required = {k: self.solver.Value(v) for k, v in self.model.required.items() if self.solver.Value(v) > 0}
        self.sources = {k: self.solver.Value(v) for k, v in self.model.sources.items() if self.solver.Value(v) > 0}
        self.providing: dict[tuple[int, Resource], dict[cp_model.IntVar, int]] = {}  # tuple[int, Resource]] should be a type, maybe want to un-nest this dicts in dict and just have tuple key
        for k, v in self.model.providing.items():
            self.providing[k] = {}
            for var in v:
                value = self.solver.Value(var)
                if value == 0:
                    continue
                if not isinstance(var, cp_model.IntVar):
                    raise IntValueException("Solution doesn't currently handle non-zero ints as var values. Can you provide an IntVar instead?")
                self.providing[k][var] = value
        # BAKERT a mana_spend of 0 is not actually possible but maybe that's not super important
        # BAKERT worst_score here should try to be "worst score that would pass as a solution" not "worst possible score", I think? Does it matter? Clusters all the decks in 0.9x range?
        # BAKERT it would be really good to make the worst total_lands a lot lower but how would we do that? some deck might really want to play max lands? one drops in every color with only basics available or whatever. maybe we can use "if you solved the problem with just basics"? that's a whole other solve but presumably a quick one1
        worst_score = score({"normalized_mana_spend": 0, "total_lands": self.model.deck.size, "pain": self.model.deck.size, "total_colored_sources": 0}, model.weights)
        # BAKERT put the normalizing stuff on Turn, probably, to avoid this monstrosity
        best_score = score({"normalized_mana_spend": normalized_mana_spend(self.model.deck.fundamental_turn, self.model.deck.fundamental_turn.max_mana_spend), "total_lands": self.min_lands, "pain": 0, "total_colored_sources": len(self.model.deck.colors) * self.min_lands}, model.weights)
        self.normalized_score = (self.objective - worst_score) / (best_score - worst_score)

    @property
    def total_lands(self) -> int:
        return sum(self.lands.values())

    def scores(self) -> dict[str, int]:
        # BAKERT could make an object not a dict. in a way scores and weights are the same thing???
        return {k.name: getattr(self, k.name) for k in fields(self.model.weights)}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Solution):
            return NotImplemented
        # BAKERT there's a lot going on here this is wrong, they aren't the same, are they?
        return self.normalized_score == other.normalized_score

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Solution):
            return NotImplemented
        return self.normalized_score < other.normalized_score

    # BAKERT entirely aside from whether we need to calculate it or not, if a constraint line is entirely counterfeited by another, elide it
    # 1    Constraint T5 2RRR
    # 2    T5 R required=9 sources=15 providing=4 Mountain, 3 Battlefield Forge, 4 Cascade Bluffs, 4 Shivan Reef
    # 3    T5 RR required=15 sources=19 providing=4 Mountain, 3 Battlefield Forge, 8 Cascade Bluffs T5 2RRR RR, 4 Shivan Reef
    # 4    T5 RRR required=19 sources=19 providing=4 Mountain, 3 Battlefield Forge, 8 Cascade Bluffs T5 2RRR RR, 4 Shivan Reef
    # 5    T5 untapped required=24 sources=24 providing=4 Mountain, 2 Island, 4 Plains, 3 Battlefield Forge, 4 Cascade Bluffs T5, 4 Shivan Reef, 3 Mystic Gate T5
    # -- Lines 3 here is entirely counterfeited by Line 2 and can be omitted?
    # -- Sources should know what land is their source even if they're new vars?

    def __repr__(self) -> str:
        optimality = "not " if self.status != cp_model.OPTIMAL else ""
        s = f"Solution ({optimality}optimal)\n\n"
        s += f"{self.total_lands} Lands (min {self.min_lands})\n\n"
        s += f"Mana spend: {self.mana_spend}/{self.model.deck.fundamental_turn.max_mana_spend} ({self.normalized_mana_spend}/21)\n"  # BAKERT magic number 21 (triangle(Turn(6))
        s += f"Pain: {self.pain}\n"
        s += f"Colored sources: {self.total_colored_sources}\n"
        s += "\n"
        for land in sorted(self.lands):
            s += f"{self.lands[land]} {land}\n"
        s += "\n"
        for constraint in sorted(self.model.deck.constraints):
            s += f"Constraint {constraint}\n"
            resources = sorted(constraint.color_combinations()) + [Aspect.UNTAPPED]
            for resource in resources:
                s += f"{constraint.turn} {resource} "
                s += f"required={self.required.get((constraint.turn, resource), 0)} "
                s += f"sources={self.sources.get((constraint.turn, resource), 0)} "
                s += "providing=" + ", ".join(f"{value} {var.name}" for var, value in self.providing.get((constraint.turn, resource), {}).items()) + "\n"
            s += "\n"
        s += f"Score: {round(self.normalized_score, 2)} ({self.objective})\n"
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
    turn = turn if turn else generic + len(colors)
    return Constraint(ManaCost(*parts), Turn(turn))


def make_deck(*args: Constraint | int) -> Deck:
    constraints, size = set(), None
    for arg in args:
        if isinstance(arg, Constraint):
            constraints.add(arg)
        elif isinstance(arg, int) and size is None:
            size = arg
        else:
            raise ValueError(type(arg), arg)
    return Deck(frozenset(constraints), size or 60)


# BAKERT need some way to say "the manabase must include 4 Shelldock Isle"
def solve(deck: Deck, weights: Weights, lands: frozenset[Land], forced_lands: Manabase | None = None) -> Solution | None:
    # BAKERT T2 RR completely counterfeits T2 R so there's no point in frank returning R=13, but you still need R in BR or BBR
    if not forced_lands:
        forced_lands = {}
    model = define_model(deck, weights, lands, forced_lands)  # BAKERT make forced_lands optional?
    solver = cp_model.CpSolver()
    status = solver.solve(model.model)  # BAKERT would be nice to not stutter here
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        return None
    return Solution(status, model, solver)


# BAKERT this function is too large, break it up
def define_model(deck: Deck, weights: Weights, lands: frozenset[Land], forced_lands: Manabase) -> Model:
    possible_lands = viable_lands(deck.colors, lands)
    model = Model(deck, possible_lands, weights, forced_lands)

    # BAKERT add_to_model is not the right name unless we generalize it
    # BAKERT treating each constraint as independent isn't quite right. If you sac a land for RR to play something you can't sac it for UU to play something else, so it's not totally independent
    # So we need to ask lands "add_to_model" passing in all constraints?

    sources: dict[Constraint, dict[ColorCombination, list[IntVar]]] = {}
    for constraint in deck.constraints:
        sources[constraint] = {}
        # BAKERT this is not quite right because of Ancient Tomb and so on
        if constraint.turn == constraint.required.mana_value:
            required_untapped = need_untapped(constraint.turn, deck.size)
        else:
            required_untapped = 0
        for land in model.lands:
            # BAKERT if you ask about U on turn 2 as part of UU and part of UW and part of 1U we want to be able to give different answers without them all being added together
            contributions = land.add_to_model(model, constraint)
            for color_combination, contribution in contributions.items():
                if color_combination not in sources[constraint]:
                    sources[constraint][color_combination] = []
                sources[constraint][color_combination].append(contribution)
        requirements = frank(constraint, deck.size)
        for color_combination, required in requirements.items():
            r = model.new_required(constraint.turn, color_combination)
            model.add(r == required)
            model.add(sum(sources[constraint][color_combination]) >= required)

        if required_untapped:  # BAKERT maybe we want to store all the lands that will be untapped this turn under sources even though we don't need any, and add a providing too
            # BAKERT this whole section isn't really how we do things now, push the color checking/generic part into the Land classes?
            generic_ok = len(constraint.required.pips) > len(constraint.required.colored_pips)
            admissible_untapped = {}
            for land, var in model.lands.items():
                makes_one_of_the_colors = any(land.can_produce_any(colors) for colors in frank(constraint, deck.size))
                if generic_ok or makes_one_of_the_colors:
                    admissible_untapped[land] = var
            lands_that_are_untapped_this_turn = [land.untapped_rules(model, constraint.turn) for land in admissible_untapped]
            model.new_providing(constraint.turn, Aspect.UNTAPPED, lands_that_are_untapped_this_turn)
            untapped_this_turn = sum(lands_that_are_untapped_this_turn)
            untapped_sources = model.new_sources(constraint.turn, Aspect.UNTAPPED)
            model.add(untapped_sources == untapped_this_turn)
            untapped = model.new_required(constraint.turn, Aspect.UNTAPPED)
            # BAKERT somewhere in all this we've stopped storing ALL vars, so we can't inspect the whole mess
            model.add(untapped == untapped_this_turn)
            model.add(untapped_this_turn >= required_untapped)

    for constraint, contributions_by_color in sources.items():
        for color_combination, contribs in contributions_by_color.items():
            # BAKERT not a great name
            sources_of_this = model.new_sources(constraint.turn, color_combination)  # BAKERT this overwrites an existing var and is pointless (in color_vars)
            model.add(sources_of_this == sum(contribs))  # BAKERT is there a better or more standard way of providing these vars that also do work?
            model.new_providing(constraint.turn, color_combination, contribs)  # BAKERT probably a better way to do this
            model.add(sum(sources[constraint][color_combination]) == sum(contribs))

    model.add(model.min_lands == max(num_lands_required(constraint, deck.size) for constraint in deck.constraints))  # BAKERT we can do this on deck now, and other things too presumably
    model.add(model.total_lands == sum(model.lands.values()))
    model.add(model.total_lands >= model.min_lands)

    mana_spend = model.mana_spend
    max_mana_spend_per_turn, mana_spend_per_turn = [], []
    fundamental_turn = max(constraint.turn for constraint in deck.constraints)
    for turn in range(1, fundamental_turn + 1):
        turn = Turn(turn)
        # BAKERT the other place where we do this kind of thing we use admissible_untapped not land_vars … is this a bug? Does it matter?
        untapped_this_turn = sum(land.untapped_rules(model, turn) for land in model.lands)
        # BAKERT this isn't quite right it's kind of 1, turn (independently executed) and it's kind of turn, turn (if you spent every turn so far)
        needed = num_lands(turn, turn, deck.size)
        enough_untapped = model.new_bool_var((turn, "can spend mana"))  # BAKERT get consistent about underscores or whatever
        model.add(untapped_this_turn >= needed).OnlyEnforceIf(enough_untapped)
        model.add(untapped_this_turn < needed).OnlyEnforceIf(enough_untapped.Not())
        max_mana_spend_this_turn = model.new_int_var(turn, turn, (turn, "max_mana_spend"))
        model.add(max_mana_spend_this_turn == turn)
        max_mana_spend_per_turn.append(max_mana_spend_this_turn)
        mana_spend_this_turn = model.new_int_var(turn - 1, turn, (turn, "mana_spend"))
        model.add(mana_spend_this_turn == turn).OnlyEnforceIf(enough_untapped)
        model.add(mana_spend_this_turn == turn - 1).OnlyEnforceIf(enough_untapped.Not())
        mana_spend_per_turn.append(mana_spend_this_turn)
    model.add(mana_spend == sum(mana_spend_per_turn))
    model.add(model.normalized_mana_spend == normalized_mana_spend(Turn(fundamental_turn), mana_spend))

    # BAKERT this should maybe be modeled as pain spent in first N turns rather than just how many painlands
    # BAKERT t1 combo don't care about pain, t20 control cares a lot, I think?
    # BAKERT should this be pushed into add_to_model? Should everything?
    pain = model.pain
    model.add(pain == sum(model.lands[land] for land in model.lands if land.painful))

    # Give a little credit for extra sources. if you can double spell sometimes more your manabase is better
    all_colored_sources = []
    # BAKERT this should be points for excess not just points
    # BAKERT but this should give more weight to B if you have 9 B spells and one W spell
    # BAKERT and earlier matters somehow?
    for color in deck.colors:
        contributing_lands = sum([var for land, var in model.lands.items() if color in land.produces])
        colored_sources = model.new_int_var(0, deck.size, (color, "colored_sources"))
        model.add(colored_sources == contributing_lands)
        all_colored_sources.append(contributing_lands)
    total_colored_sources = model.total_colored_sources
    model.add(total_colored_sources == sum(all_colored_sources))

    # BAKERT if a deck is playing 5+ drops it cares less about fitting in 24 lands than a deck curving out to 4
    # BAKERT total_colored_sources is too powerful in this equation so we need to tweak but let's save tweaking until we have done the above
    # BAKERT it's weird that we're using model.total_lands here (and model.min_lands above) but we're using local vars for the others
    # BAKERT relying on the model having vars with the same names as the weights feels a little fragile. Can we make it more related?
    model.maximize(model.objective_function())

    return model


def viable_lands(colors: frozenset[Color], lands: frozenset[Land]) -> frozenset[Land]:
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
def num_lands_required(constraint: Constraint, deck_size: int) -> int:
    return num_lands(constraint.required.mana_value, constraint.turn, deck_size)


def need_untapped(turn: Turn, deck_size: int) -> int:
    try:
        return frank(Constraint(ManaCost(C), turn), deck_size)[ColorCombination({C})]
    except UnsatisfiableConstraint:
        # We don't know how many untapped lands you need beyond turn 6 so supply an overestimate
        return frank(Constraint(ManaCost(C), Turn(6)), deck_size)[ColorCombination({C})]  # BAKERT 6 is a magic number here and shared with normalize_mana_spend


class UnsatisfiableConstraint(Exception):
    pass


# https://www.channelfireball.com/article/how-many-sources-do-you-need-to-consistently-cast-your-spells-a-2022-update/dc23a7d2-0a16-4c0b-ad36-586fcca03ad8/
def frank(constraint: Constraint, deck_size: int) -> dict[ColorCombination, int]:  # BAKERT how to mypy that the ColorCombinations must contain only Colors?
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
    color_set = constraint.color_combinations()
    results = {}
    for colors in color_set:
        num_pips = len(colors)
        req = table.get((num_pips, constraint.turn), {}).get(deck_size)
        if not req:
            raise UnsatisfiableConstraint(f"{num_pips} {constraint.turn} {deck_size}")
        results[colors] = req
    return results


def num_lands(mana_value: int, turn: Turn, deck_size: int) -> int:
    try:
        return frank(Constraint(turn=turn, required=ManaCost(*[W] * mana_value)), deck_size)[ColorCombination([W] * mana_value)]
    except UnsatisfiableConstraint:
        # We are at mana value 5 or beyond, return an underestimate, but better than nothing
        return frank(Constraint(turn=Turn(4), required=ManaCost(*[W] * 4)), deck_size)[ColorCombination([W] * 4)]


# BAKERT you should never choose Crumbling Necropolis over a check or a snarl in UR (or UB or RB) if you have even one land with the right basic types
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

# BAKERT
# Mana costs are tuples because they (kinda) have an order
# Color combinations are FrozenMultisets and do not have an order
# But in a sense these are the same thing - {1}{B}{R} being pretty similar to {B}{R} so maybe they should both use the same representation?
# perhaps best of all is if mana costs are frozen multisets but something knows how to present them in the right order?

# BAKERT Now that multiset supports mypy I should be able to say x: FrozenMultiset[Color] but this causes a runtime error

# BAKERT why is T3 untapped required and T4 untapped required both 24? surely it should change as mana cost changes?
