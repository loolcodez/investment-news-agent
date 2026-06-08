## Quick Start

To run this app, open terminal in the `investment-news-agent` folder and run:
```bash
make run
```

The server will start listening on **port 8000**. You can change the port in the `makefile`.

This command will also automatically install all dependencies defined in the `Pipfile`.

## Available Make Commands

### `make run`
Run the application. Also installs all dependencies when needed.

### `make setup`
Install dependencies defined in the `Pipfile` into the virtual environment.  
Use this after adding new dependencies to `Pipfile`.

### `make env`
Enter the pipenv shell for interactive work.  
Only needed if you want to run commands interactively in the virtual environment.

### `make clean`
Remove cache files and delete the virtual environment to free up space.

### `make clean-all`
Complete clean including removal of `Pipfile.lock`.

**Note:** Virtual environment is created at `~/.local/share/virtualenvs`

The location varies by operating system:
- **Linux/macOS:** `~/.local/share/virtualenvs/`
- **Windows:** `%USERPROFILE%\.virtualenvs\`

To create the virtual environment inside the project folder instead (as `.venv`), set:
```bash
export PIPENV_VENV_IN_PROJECT=1
```