.PHONY: dev test lint fixture smoke clean

API_BASE_URL ?= http://localhost:8000

dev:
	docker compose up --build api

test:
	pytest -x --tb=short

lint:
	python3 -m ruff check .

fixture:
	python3 run_all.py --fixture

smoke:
	./scripts/smoke_api.sh $(API_BASE_URL)

clean:
	docker compose down --volumes --remove-orphans
