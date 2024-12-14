# Prerequisite
1. Python 3.12
2. Docker
3. [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Create Python virtual environment and install dependencies
```bash
uv python install 3.12
uv sync
```

### Activate Python virtual environment
```bash
source .venv/bin/activate
```

### Run app and database through Docker
```bash
docker compose up -d
```

### Run database migration
```bash
alembic upgrade head
```

### Run data dump
```bash
python utils/dump_csv_data.py
```


Access API docs locally via [localhost:8000](http://localhost:8000).