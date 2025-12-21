.PHONY: setup lint lint-fix run dev build test clean deploy

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
NPM := npm

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	cd web && $(NPM) install
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"

# Development: run Flask and Vite dev server concurrently
# Uses npx concurrently to manage both processes (Ctrl+C kills both)
dev:
	npx concurrently --kill-others --names "flask,vite" \
		"$(PYTHON) -m src.app" \
		"cd web && $(NPM) run dev"

# Production build
build:
	cd web && $(NPM) run build

lint:
	$(RUFF) check src/
	$(RUFF) format --check src/
	$(MYPY) src/
	cd web && $(NPM) run typecheck && $(NPM) run lint

lint-fix:
	$(RUFF) check --fix src/
	$(RUFF) format src/
	cd web && $(NPM) run lint:fix

run:
	$(PYTHON) -m src.app

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -rf $(VENV)
	rm -rf __pycache__ src/__pycache__ src/**/__pycache__
	rm -rf .mypy_cache .ruff_cache
	rm -rf *.egg-info
	rm -rf web/node_modules
	rm -rf static/assets
	find . -type f -name "*.pyc" -delete

deploy:
	@mkdir -p ~/.config/systemd/user
	cp -f ai-chatbot.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable ai-chatbot
	systemctl --user restart ai-chatbot
	@echo "Deployed. View logs with: journalctl --user -u ai-chatbot -f"
