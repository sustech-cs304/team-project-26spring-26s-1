FROM docker.io/astral/uv:trixie

WORKDIR /app
EXPOSE 8000

COPY . .

RUN uv sync

ENTRYPOINT ["uv", "run", "uvicorn", "src.agent.main:app", "--host", "0.0.0.0"]