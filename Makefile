.PHONY: dev test test-backend test-frontend lint fixture smoke clean

API_BASE_URL ?= http://localhost:8000

dev:
	docker compose up --build api

test: test-backend test-frontend

test-backend:
	pytest -x --tb=short

test-frontend:
	npm test

lint:
	python3 -m ruff check .

fixture:
	python3 run_all.py --fixture

smoke:
	./scripts/smoke_api.sh $(API_BASE_URL)

clean:
	docker compose down --volumes --remove-orphans
