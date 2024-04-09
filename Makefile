.PHONY: test lint types

test:
	pytest --ignore=lib

lint:
	black --line-length 1000000 .

types:
	mypy --no-incremental --disallow-untyped-defs --disallow-incomplete-defs .

all: lint types test
