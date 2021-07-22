check:
	poetry run black pdscheduling tests --check
	poetry run mypy .

test:
	poetry run pytest --block-network

black:
	poetry run black pdscheduling tests

prepare:
	poetry run mypy --install-types

deploy: check test
	poetry publish --build
