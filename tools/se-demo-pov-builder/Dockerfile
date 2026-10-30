# Multi-stage build: compile the UI, then run the API serving it.
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/ /app/backend/
RUN pip install --no-cache-dir /app/backend
COPY personas/ /app/personas/
COPY knowledge/ /app/knowledge/
COPY workflows/ /app/workflows/
COPY adapters/ /app/adapters/
COPY --from=ui /ui/dist /app/frontend/dist
RUN useradd --create-home --uid 10001 sepb && mkdir -p /app/data && chown sepb /app/data
USER sepb
# Inside the container the server must listen on all interfaces; docker-compose.yml
# publishes the port on 127.0.0.1 only.
ENV SEPB_HOST=0.0.0.0 \
    SEPB_CONTENT_DIR=/app \
    SEPB_DATA_DIR=/app/data \
    SEPB_FRONTEND_DIST=/app/frontend/dist
EXPOSE 8000
CMD ["python", "-m", "se_pov_builder"]
