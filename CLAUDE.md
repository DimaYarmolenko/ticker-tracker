# Project
This is a Fast API app that uses sqlalchemy and sqllite database.

# Code Style
- Use type hints
- Try to use enums instead of magic strings or plain values if possible.

# Tests
The tests are located in @tests/ folder, writen with PyTest and have test database with fixtures that mimics the application database.

# Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For development (linter & formatter):
```bash
pip install -r requirements-dev.txt
```

# Commands
```bash
# Run tests
python -m pytest tests/ -v
```

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI) at `http://localhost:8000/docs`.

```bash
# Check for lint errors
ruff check .

# Fix lint errors automatically
ruff check --fix .

# Format code
ruff format .

# Check formatting without applying changes
ruff format --check .
```
