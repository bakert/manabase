from manabase_solver import DEFAULT_WEIGHTS, B, Constraint, Deck, G, ManaCost, R, Turn, U, W, card, make_deck, penny_dreadful_lands, solve

# To use these scraps from the commandline install the library, maybe with `pip install -e .`

DeputyOfDetention = Constraint(ManaCost(1, U, W), Turn(3))

BurstLightningOnTurnTwo = Constraint(ManaCost(R), Turn(2))
BurstLightning = card("R")
MemoryLapse = Constraint(ManaCost(1, U), Turn(2))
PestermiteOnTurnFour = Constraint(ManaCost(2, U), Turn(4))
RestorationAngel = Constraint(ManaCost(3, W))
KikiJikiMirrorBreaker = Constraint(ManaCost(2, R, R, R), Turn(5))
Disenchant = Constraint(ManaCost(1, W), Turn(2))
LightningHelix = card("RW")
Forbid = Constraint(ManaCost(1, U, U), Turn(3))
OptOnTurnTwo = card("U", 2)
Pestermite = card("2U")
AncestralVision = card("U")

KikiOnSix = card("2RRR", 6)

jeskai_twin_base = frozenset({BurstLightningOnTurnTwo, MemoryLapse, Pestermite, RestorationAngel})
jeskai_twin = Deck(frozenset(jeskai_twin_base | {KikiJikiMirrorBreaker}), 60)
jeskai_twin_with_the_ravens_warning = Deck(frozenset(jeskai_twin.constraints | {DeputyOfDetention}), 60)
jeskai_twin_but_dont_rush_kiki = Deck(frozenset(jeskai_twin_base | {KikiOnSix}), 60)

CracklingDrake = card("UURR")

GloryBringer = card("3RR")
AcademyLoremaster = card("UU")

KikiOnSix = card("2RRR", 6)

izzet_twin = make_deck(BurstLightningOnTurnTwo, MemoryLapse, Pestermite, KikiOnSix)
izzet_twin_with_loremaster = Deck(frozenset(izzet_twin.constraints | {AcademyLoremaster}), 60)

BenevolentBodyguard = Constraint(ManaCost(W), Turn(1))
MeddlingMage = Constraint(ManaCost(U, W), Turn(2))
SamuraiOfThePaleCurtain = Constraint(ManaCost(W, W), Turn(2))

azorius_taxes = make_deck(BenevolentBodyguard, MeddlingMage, SamuraiOfThePaleCurtain, DeputyOfDetention)

SettleTheWreckage = Constraint(ManaCost(2, W, W), Turn(4))
VenserShaperSavant = card("2UU")

azorius_taxes_postboard = Deck(frozenset(azorius_taxes.constraints | {SettleTheWreckage}), 60)

mono_w_bodyguards = make_deck(BenevolentBodyguard)
white_weenie = make_deck(BenevolentBodyguard, SamuraiOfThePaleCurtain)
meddlers = make_deck(MeddlingMage)

# BAKERT frank currently says UnsatisfiableConstraint to manacosts with 5+ colors
InvasionOfAlara = Constraint(ManaCost(W, U, B, R, G), Turn(5))
invasion_of_alara = make_deck(InvasionOfAlara)

Duress = card("B")
Abrade = card("1R")
DigThroughTime = card("UU", 5)
WrathOfGod = card("2WW", 4)

popular = make_deck(MemoryLapse, Abrade, DigThroughTime, WrathOfGod)

BaskingRootwalla = card("G")
PutridImp = card("B")
LotlethTroll = card("BG")
LotlethTrollWithRegen = card("BBG")

golgari_madness = make_deck(PutridImp, LotlethTroll)

GrimLavamancer = card("R")
Pteramander = card("U")
LogicKnot = card("1UU")

gfabsish = make_deck(GrimLavamancer, Pteramander, VenserShaperSavant)

Assault = card("R", 2)
LagoonBreach = card("1U")
MadcapExperiment = card("3R")
Away = card("2B")
ChainOfPlasma = card("1R")

my_invasion_of_alara = make_deck(Assault, LagoonBreach, MadcapExperiment, Away, InvasionOfAlara, ChainOfPlasma)

GiantKiller = card("W")
KnightOfTheWhiteOrchid = card("WW")
SunTitan = card("4WW")

emeria = make_deck(GiantKiller, KnightOfTheWhiteOrchid, SunTitan)

PriestOfFellRites = card("WB")
HaakonStromgaldScourge = card("1BB", 5)
MagisterOfWorth = card("4WB")
OptOnTurn2 = card("U", 2)
SearchForAzcanta = card("1U")
CouncilsJudgment = card("1WW", 4)
EsperCharm = card("WUB")
ForbidOnTurnFour = card("1UU", 4)
WrathOfGod = card("2WW")

gifts = make_deck(PriestOfFellRites, HaakonStromgaldScourge, MagisterOfWorth, OptOnTurn2, SearchForAzcanta, CouncilsJudgment, EsperCharm, ForbidOnTurnFour, WrathOfGod)

actual_twin = make_deck(GrimLavamancer, Pteramander, KikiJikiMirrorBreaker, DigThroughTime)

# Crypt of Agadeem possibly beyond simulation :)
LamplightPhoenix = card("1RR")
BigCyclingTurn = card("BBB")
BringerOfTheLastGift = card("6BB")
StarvingRevenant = card("2BB")
ArchfiendOfIfnir = card("3BB")

midnight_phoenix = make_deck(LamplightPhoenix, BigCyclingTurn, StarvingRevenant, ArchfiendOfIfnir)

Cremate = card("B")
GlimpseTheUnthinkable = card("UB")

mill = make_deck(Cremate, GlimpseTheUnthinkable, DigThroughTime)

HomeForDinner = card("1W")
GeologicalAppraiser = card("2RR")
SuspendGlimpseOnTwo = card("RR")
SuspendGlimpseOnThree = card("RR", 3)
CavalierOfDawn = card("2WWW")
ChancellorOfTheForge = card("4RRR")
EtalisFavor = card("2R")

glimpse = make_deck(HomeForDinner, GeologicalAppraiser, EtalisFavor)

SeismicAssault = card("RRR")
SwansOfBrynArgoll = card("2UU")

seismic_swans = make_deck(SeismicAssault, SwansOfBrynArgoll)

NecroticOoze = card("2BB")
GiftsUngiven = card("3U")
TaintedIndulgence = card("UB")
BuriedAlive = card("2B")

ooze = make_deck(NecroticOoze, PriestOfFellRites, TaintedIndulgence, GiftsUngiven, BuriedAlive)

BloodsoakedChampion = card("B")
UnluckyWitness = card("R")
DreadhordeButcher = card("BR")
LightningSkelemental = card("BRR")

skelemental_sac = make_deck(BloodsoakedChampion, UnluckyWitness, DreadhordeButcher, LightningSkelemental)

Korlash = card("2BB")
Lashwrithe = card("4")
PlagueStinger = card("1B")

mono_b_infect = [Korlash, Lashwrithe, PlagueStinger]

ArchiveDragon = card("4UU")
NorinTheWary = card("R")

our_deck = make_deck(NorinTheWary, ArchiveDragon)

CenoteScout = card("G")
CenoteScoutOnTwo = card("G", 2)
MasterOfThePearlTrident = card("UU")
KumenaTyrantOfOrazca = card("1GU")

ug_merfolk = make_deck(CenoteScoutOnTwo, MasterOfThePearlTrident, KumenaTyrantOfOrazca)

splash_gifts_ooze = make_deck(NecroticOoze, PriestOfFellRites, GiftsUngiven, BuriedAlive)

wb_ooze = make_deck(NecroticOoze, PriestOfFellRites)

KarmicGuide = card("3WW")
ConspiracyTheorist = card("1R")
ooze_kiki = make_deck(ConspiracyTheorist, KarmicGuide, KikiJikiMirrorBreaker, PriestOfFellRites, RestorationAngel, BuriedAlive, BurstLightningOnTurnTwo)

OustOnTwo = card("W", 2)
TheRavensWarning = card("1UW")
ravens_warning = make_deck(MemoryLapse, OustOnTwo, CouncilsJudgment, Forbid, TheRavensWarning, WrathOfGod)

datro = make_deck(card("WU"), card("4RR"), 80)

Attrition = card("1BB")
BitterTriumph = card("1B")
clerics = make_deck(BitterTriumph, WrathOfGod, Attrition)

OutOfAir = card("UU")
Doomskar = card("1WW")
GideonJura = card("3WW")
control = make_deck(OutOfAir, Doomskar, GideonJura)

datro_orzhov = make_deck(card("1B"), card("1W"), card("2WW"))

game_objects = make_deck(card("UG"), card("2UB"), card("WG"))

print(solve(game_objects, DEFAULT_WEIGHTS, penny_dreadful_lands))
