test:
	poetry run black pdscheduling --check
	poetry run mypy .
	poetry run pytest --block-network

black:
	poetry run black pdscheduling

prepare:
	poetry run mypy --install-types
