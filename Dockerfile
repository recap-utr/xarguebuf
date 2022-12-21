ARG POETRY_VERSION=1.3.1
ARG PYTHON_VERSION=3.9

FROM python:${PYTHON_VERSION}-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV cmd="--help"

WORKDIR /app

RUN apt update && \
    apt install -y graphviz  graphviz-dev build-essential curl && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"
RUN curl -sSL https://install.python-poetry.org | python -

COPY poetry.lock* pyproject.toml ./
RUN poetry install --no-interaction --no-ansi --no-root
COPY twitter2arguebuf ./twitter2arguebuf

CMD [ "sh", "-c", "poetry run python -m twitter2arguebuf ${cmd}" ]
