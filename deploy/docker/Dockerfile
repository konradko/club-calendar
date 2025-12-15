FROM python:3.11-alpine

RUN apk add --no-cache tzdata

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace config and package sources
COPY pyproject.toml uv.lock ./
COPY packages/core packages/core
COPY packages/cli packages/cli

# Install only the packages we need (core, cli)
RUN uv sync --frozen --no-dev --package club-calendar-cli

ENV TZ="UTC"
ENV SYNC_SCHEDULE="0 8,12,16,20 * * *"
ENV PORT=51470

EXPOSE 51470

COPY deploy/docker/entrypoint.sh .
CMD ["sh", "entrypoint.sh"]
