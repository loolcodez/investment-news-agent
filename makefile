SHELL := bash
.ONESHELL:
.SHELLFLAGS := -ecx
PYTHON := python3
PORT := 8000
SUMMARY_HOURS ?= 24
SUMMARY_MIN_REL ?= 7
SUMMARY_OUTPUT ?= reports/daily-summary.md

# Call this only if you need to enter shell and work interactive there
env:
	pipenv install --dev
	pipenv shell

# You can call this directly to install dependencies defined in Pipfile in the virtual env
# You could call this also after you have added new dependencies in Pipfile
setup:
	pipenv install --dev

# Call this if you want to run the app. This will also install all dependencies in defined pipfile in the virtual env
run: setup
	pipenv run uvicorn app.main:app --reload --log-config log_settings.yaml --port $(PORT)

news-agent: setup
	pipenv run python -m app.main_cli agent --config config.yaml

daily-summary: setup
	pipenv run python -m app.main daily-summary --hours $(SUMMARY_HOURS) --min-relevance $(SUMMARY_MIN_REL) --output $(SUMMARY_OUTPUT)

# Virtual env is created here: ~/.local/share/virtualenvs
# Call this when you want to free up space or reset all dependencies
# pipenv --rm should remove the virtual env 
clean:
	rm -rf __pycache__
	rm -rf app/__pycache__
	rm -rf .pytest_cache
	rm -rf ./app.log
	pipenv --rm

# Call this to do a complete clean including removing the Pipfile.lock
clean-all: clean
	rm -rf Pipfile.lock
