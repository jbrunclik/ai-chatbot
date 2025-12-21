.PHONY: setup lint lint-fix run test clean deploy

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
NPM := npm
ESLINT := npx eslint

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@if [ ! -d "node_modules" ]; then \
		$(NPM) install; \
	fi
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"

lint:
	$(RUFF) check src/
	$(RUFF) format --check src/
	$(MYPY) src/
	$(ESLINT) src/static/*.js

lint-fix:
	$(RUFF) check --fix src/
	$(RUFF) format src/
	$(ESLINT) --fix src/static/*.js

run:
	$(PYTHON) -m src.app

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -rf $(VENV)
	rm -rf __pycache__ src/__pycache__ src/**/__pycache__
	rm -rf .mypy_cache .ruff_cache
	rm -rf *.egg-info
	rm -rf node_modules
	find . -type f -name "*.pyc" -delete

deploy:
	@mkdir -p ~/.config/systemd/user
	cp -f ai-chatbot.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable ai-chatbot
	systemctl --user restart ai-chatbot
	@echo "Deployed. View logs with: journalctl --user -u ai-chatbot -f"
