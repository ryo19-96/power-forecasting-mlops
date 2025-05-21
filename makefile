.PHONY: lint fmt all zip_lambda model_pipeline deploy_pipeline run_api
# === Ruff ===

lint:
	poetry run ruff check

fmt:
	poetry run ruff check --fix

all: fmt lint

# === Pipeline ===
model_pipeline:
	poetry run python pipeline/model_pipeline/run_pipeline.py

deploy_pipeline:
	poetry run python pipeline/deployment_pipeline/deployment_pipeline.py

# === zip ===
zip_lambda:
	@if [ -z "$(file)" ]; then \
		echo "Usage: make zip_lambda file=file_name (without extension)"; \
		exit 1; \
	fi
	cd lambda && zip -j $(file).zip $(file).py
	@echo "completed $(file).zip"

# === API ===
run_api:
	poetry run uvicorn inference_api.main:app --reload --port 8000
