FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
WORKDIR /code
COPY pyproject.toml uv.lock /code/
# Install the application dependencies.
RUN uv sync --frozen --no-cache

# Place executables in the environment at the front of the path
ENV PATH="/code/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Run the application.
CMD ["fastapi", "run", "app/main.py", "--port", "8000", "--host", "0.0.0.0"]