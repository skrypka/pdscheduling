check:
	poetry run black pdscheduling --check
	poetry run mypy .

test:
	poetry run pytest --block-network

black:
	poetry run black pdscheduling

prepare:
	poetry run mypy --install-types

deploy: check test
	poetry publish --build
