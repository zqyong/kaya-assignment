# Prerequisite
1. Python 3.12
2. Docker

### Create Python virtual environment and install dependencies
```bash
uv sync
```

### Activate Python virtual environment
```bash
source .venv/bin/activate
```

### Run database migration
```bash
alembic upgrade head
```

### Run data dump
```bash
python utils/dump_csv_data.py
```