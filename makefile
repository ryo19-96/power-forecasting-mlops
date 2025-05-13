.PHONY: lint format all

lint:
	poetry run ruff check

fmt:
	poetry run ruff check --fix

all: lint fmt