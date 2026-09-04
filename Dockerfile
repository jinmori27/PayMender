FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY frontend/ ./
RUN mkdir -p /app/backend/static && pnpm build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
WORKDIR /app
COPY backend/requirements.lock ./backend/requirements.lock
RUN python -m pip install --no-cache-dir -r backend/requirements.lock
COPY backend/app ./backend/app
COPY --from=frontend-build /app/backend/static ./backend/static
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
