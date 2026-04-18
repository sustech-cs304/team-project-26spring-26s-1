FROM docker.io/astral/uv:trixie

ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple \
    UV_DEFAULT_INDEX=https://mirrors.sustech.edu.cn/pypi/web/simple

WORKDIR /app
EXPOSE 8000

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i \
            -e 's|https\?://deb.debian.org/debian|https://mirrors.sustech.edu.cn/debian|g' \
            -e 's|https\?://deb.debian.org/debian-security|https://mirrors.sustech.edu.cn/debian-security|g' \
            -e 's|https\?://security.debian.org/debian-security|https://mirrors.sustech.edu.cn/debian-security|g' \
            /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i \
            -e 's|https\?://deb.debian.org/debian|https://mirrors.sustech.edu.cn/debian|g' \
            -e 's|https\?://deb.debian.org/debian-security|https://mirrors.sustech.edu.cn/debian-security|g' \
            -e 's|https\?://security.debian.org/debian-security|https://mirrors.sustech.edu.cn/debian-security|g' \
            /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends nodejs; \
    if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then \
        ln -sf "$(command -v nodejs)" /usr/local/bin/node; \
    fi; \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN uv sync

ENTRYPOINT ["uv", "run", "uvicorn", "src.agent.main:app", "--host", "0.0.0.0"]
