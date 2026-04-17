FROM docker.io/astral/uv:trixie

WORKDIR /app
EXPOSE 8001

COPY . .

RUN uv virtualenv && \
    . .venv/bin/activate && \
    uv pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["uv", "run",  "python", "user.py"]
