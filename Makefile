.PHONY: run fmt lint type test cov reset-qdrant

run:
	EMBEDDING_BACKEND=fastembed poetry run uvicorn api.main:app --host 0.0.0.0 --port 8080

fmt:
	poetry run ruff check --fix .
	poetry run ruff format .

lint:
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy .

type:
	poetry run mypy .

test:
	poetry run pytest -q

cov:
	poetry run pytest --cov=api --cov=clients --cov=embedding -q

reset-qdrant:
	curl -s -X DELETE http://localhost:6333/collections/news | jq .
