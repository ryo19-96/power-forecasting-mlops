.PHONY: lint format all

lint:
	poetry run ruff

format:
	poetry run ruff check --fix

all: lint format