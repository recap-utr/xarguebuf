ARG PYTHON_VERSION=3.9

FROM python:${PYTHON_VERSION}-slim

ARG POETRY_VERSION=1.3.1
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=100
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt update && \
    apt install -y graphviz  graphviz-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}" \
    && poetry config virtualenvs.in-project true

COPY poetry.lock* pyproject.toml ./
RUN poetry install --no-interaction --no-ansi --no-root

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY twitter2arguebuf ./twitter2arguebuf

ENTRYPOINT [ "python", "-m", "twitter2arguebuf" ]
CMD [ "--help" ]
