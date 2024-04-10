default:
	@echo "Try 'make all'"

imports:
	isort --skip=lib --skip=bin --line-length=10000 .

lint:
	@# E203 "whitespace after :" conflicts with black
	flake8 --max-line-length=10000 --exclude=lib --extend-ignore=E203 .

style:
	black --line-length=10000 .

types:
	mypy --no-incremental --disallow-untyped-defs --disallow-incomplete-defs .

test:
	pytest -x --ignore=lib

all: imports lint style types test
