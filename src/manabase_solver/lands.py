from .manabase_solver import B, Basic, Bicycle, C, Check, Filter, G, Pain, R, RiverOfTearsLand, Snarl, Tango, Tapland, U, W

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
s32_snarls = {ChokedEstuary, ForebodingRuins, FortifiedVillage, FrostboilSnarl, GameTrail, PortTown, VineglimmerSnarl}
# -ShineshadowSnarl, FortifiedVillage, FrostboilSnarl
snarls = {ChokedEstuary, ForebodingRuins, FurycalmSnarl, GameTrail, NecroblossomSnarl, PortTown, VineglimmerSnarl}

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
s32_filters = {CascadeBluffs, FetidHeath, FireLitThicket, FloodedGrove, GravenCairns, MysticGate, SunkenRuins, WoodedBastion}
# -FetidHeath, SunkenRuins, CascadeBluffs, TwilightMire
filters = {FireLitThicket, FloodedGrove, GravenCairns, MysticGate, RuggedPrairie, WoodedBastion}

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
# BAKERT haven't updated for S33 because they're not that interesting

GrandColiseum = Tapland("Grand Coliseum", None, "Land", (W, U, B, R, G), painful=True)
# BAKERT need to teach it that the third time you tap a vivid land it only taps for M, tricky
VividCrag = Tapland("Vivid Crag", None, "Land", (W, U, B, R, G))
VividMarsh = Tapland("Vivid Marsh", None, "Land", (W, U, B, R, G))
VividMeadow = Tapland("Vivid Meadow", None, "Land", (W, U, B, R, G))

s32_five_color_lands = {GrandColiseum, VividCrag}
five_color_lands = {GrandColiseum, VividMarsh, VividMeadow}

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
s32_painlands = {BattlefieldForge, Brushland, CavesOfKoilos, KarplusanForest, LlanowarWastes, ShivanReef, SulfurousSprings, YavimayaCoast}
# -AdarkarWastes, UndergroundRiver, SulfurousSprings, KarplusanForest
# BAKERT did AdarkarWastes make it in?
painlands = {BattlefieldForge, Brushland, CavesOfKoilos, LlanowarWastes, ShivanReef, YavimayaCoast}

PrairieStream = Tango("Prairie Stream", None, "Land - Plains Island", (W, U))
CanopyVista = Tango("Canopy Vista", None, "Land - Forest Plains", (G, W))

# BAKERT we have more tangos in S33
tangos = {PrairieStream, CanopyVista}

# BAKERT this is wrong for S33
CrumblingNecropolis = Tapland("Crumbling Necropolis", None, "Land", (U, B, R))
RiverOfTears = RiverOfTearsLand("River of Tears", None, "Land", (U, B))

# BAKERT Tendo Ice Bridge and Crumbling Vestige

penny_dreadful_lands = frozenset(basics.union(checks).union(snarls).union(bicycles).union(filters).union(five_color_lands).union(painlands).union({CrumblingNecropolis, RiverOfTears}).union(tangos).union(creature_lands).union(restless_lands))
