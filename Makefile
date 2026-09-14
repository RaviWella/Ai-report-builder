.PHONY: migrate-metadata migrate-metadata-legacy

migrate-metadata:
	cd backend && alembic upgrade head

migrate-metadata-legacy:
	cd backend && alembic -c alembic_legacy.ini upgrade head
