# manabase-solver

Magic the Gathering manabase solver

## Usage

    from manabase_solver import card, DEFAULT_WEIGHTS, make_deck, penny_dreadful_lands, solve

    Pestermite = card("2U")
    RestorationAngel = card("3W")
    KikiJikiOnTurnSix = card("2RRR", 6)
    deck = make_deck(Pestermite, RestorationAngel, KikiJikiOnTurnSix)
    solution = solve(deck, DEFAULT_WEIGHTS, penny_dreadful_lands)
    print(solution)
    print(solution.lands)

## Development

    $ git clone https://github.com/bakert/manabase-solver
    $ cd manabase-solver
    $ python3.10 -m venv .
    $ source bin/activate
    $ pip install -r requirements.txt
    $ source bin/activate
    $ pip install -e .
    $ python scripts/scratch.py
    $ pip install -r requirements-dev.txt
    $ source bin/activate
    $ make all

## Build

    $ python -m build

## Publish

    $ vi pyproject.toml  # Bump version number
    $ git add -p
    $ git commit -m "Bump version number to vX.X"
    $ git tag -a "vX.X" -m "manabase-solver vX.X"
    $ \rm -r dist
    $ python -m build
    $ twine upload dist/*

(c) 2024 Thomas David Baker <bakert@gmail.com>
