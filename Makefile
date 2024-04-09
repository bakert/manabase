.PHONY: test lint types

test:
	pytest --ignore=lib

imports:
	isort --skip=lib --skip=bin --line-length=10000 .

style:
	black --line-length-10000 .

lint:
	flake8 --max-line-length=10000 --exclude=lib --ignore=E203 .  # E203 "whitespace after :" conflicts with black

types:
	mypy --no-incremental --disallow-untyped-defs --disallow-incomplete-defs .

all: lint types test
