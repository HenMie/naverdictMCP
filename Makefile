# Makefile for Naver Dictionary MCP Server
# 提供常用命令的快捷方式

.PHONY: help install install-dev test test-cov test-perf lint format type-check security pre-commit docker-build docker-run clean

# 默认目标：显示帮助
help:
	@echo "Naver Dictionary MCP - 可用命令:"
	@echo ""
	@echo "  安装与依赖:"
	@echo "    make install       - 安装生产依赖"
	@echo "    make install-dev   - 安装开发依赖"
	@echo ""
	@echo "  测试:"
	@echo "    make test          - 运行所有测试"
	@echo "    make test-cov      - 运行测试并生成覆盖率报告"
	@echo "    make test-perf     - 运行性能基准测试"
	@echo ""
	@echo "  代码质量:"
	@echo "    make lint          - 运行 Ruff 代码检查"
	@echo "    make format        - 格式化代码"
	@echo "    make type-check    - 运行 MyPy 类型检查"
	@echo "    make security      - 运行安全检查"
	@echo "    make pre-commit    - 运行所有 pre-commit 检查"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build  - 构建 Docker 镜像"
	@echo "    make docker-run    - 运行 Docker 容器"
	@echo ""
	@echo "  清理:"
	@echo "    make clean         - 清理临时文件"

# 安装生产依赖
install:
	@echo "安装生产依赖..."
	uv sync --no-dev

# 安装开发依赖
install-dev:
	@echo "安装开发依赖..."
	uv sync
	@echo "安装 pre-commit hooks..."
	pre-commit install

# 运行所有测试
test:
	@echo "运行所有测试..."
	pytest tests/ -v

# 运行测试并生成覆盖率报告
test-cov:
	@echo "运行测试并生成覆盖率报告..."
	pytest --cov=src --cov-report=html --cov-report=term tests/
	@echo "覆盖率报告已生成: htmlcov/index.html"

# 运行性能基准测试
test-perf:
	@echo "运行性能基准测试..."
	pytest tests/test_performance.py -v -m performance -s

# 运行 Ruff 代码检查
lint:
	@echo "运行 Ruff 代码检查..."
	ruff check src/ tests/

# 格式化代码
format:
	@echo "格式化代码..."
	ruff format src/ tests/
	ruff check --fix src/ tests/

# 运行 MyPy 类型检查
type-check:
	@echo "运行 MyPy 类型检查..."
	mypy src/

# 运行安全检查
security:
	@echo "运行安全检查..."
	bandit -c pyproject.toml -r src/

# 运行所有 pre-commit 检查
pre-commit:
	@echo "运行所有 pre-commit 检查..."
	pre-commit run --all-files

# 构建 Docker 镜像
docker-build:
	@echo "构建 Docker 镜像..."
	docker build -t naver-dict-mcp:latest .

# 运行 Docker 容器
docker-run:
	@echo "运行 Docker 容器..."
	docker run -d -p 8000:8000 --name naver-dict-mcp naver-dict-mcp:latest

# 清理临时文件
clean:
	@echo "清理临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage build/ dist/ 2>/dev/null || true
	@echo "清理完成!"

