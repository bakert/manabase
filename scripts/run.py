from manabase_solver import DEFAULT_WEIGHTS, penny_dreadful_lands, solve
from manabase_solver.decks import game_objects

# To use these scraps from the commandline install the library, maybe with `pip install -e .`

print(solve(game_objects, DEFAULT_WEIGHTS, penny_dreadful_lands))
