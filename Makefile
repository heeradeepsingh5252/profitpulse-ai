.PHONY: up down logs test db-check api-check reset

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

test:
	docker compose exec api pytest -q

db-check:
	docker compose exec api python scripts/check_db.py

api-check:
	bash examples/day2_api_checks.sh

reset:
	docker compose down -v
	docker compose up --build -d
