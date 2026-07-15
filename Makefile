.PHONY: help install dev test coverage lint format type-check security check clean

help:
	@echo "Naver Dictionary MCP"
	@echo "  make install     安装锁定依赖"
	@echo "  make dev         启动本地 ASGI 服务"
	@echo "  make test        运行测试"
	@echo "  make check       运行全部质量检查"

install:
	uv sync --locked

dev:
	@test -f .env.local || { echo ".env.local is required; copy .env.example first"; exit 1; }
	@set -a; . ./.env.local; set +a; exec uv run uvicorn app:app --host 127.0.0.1 --port 3000 --reload

test:
	uv run pytest

coverage:
	uv run pytest --cov=src --cov=app --cov-report=term-missing --cov-fail-under=90

lint:
	uv run ruff check app.py src tests
	uv run ruff format --check app.py src tests

format:
	uv run ruff check --fix app.py src tests
	uv run ruff format app.py src tests

type-check:
	uv run mypy app.py src tests

security:
	uv run bandit -c pyproject.toml -r app.py src

check: lint type-check security coverage
	git diff --check

clean:
	rm -rf .coverage .mypy_cache .pytest_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
