# Makefile for local development and testing

.PHONY: install playground test lint

# Install project dependencies
install:
	uv sync

# Run the agent in the local playground UI
playground:
	uv run agents-cli playground

# Run tests
test:
	uv run pytest

# Run linting and type checks
lint:
	uv run agents-cli lint
