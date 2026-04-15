# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim
WORKDIR /app

# Install Python deps
COPY compute/pyproject.toml compute/
RUN cd compute && pip install --no-cache-dir .

# Copy compute source
COPY compute/ compute/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist frontend/dist

EXPOSE 8000

CMD ["uvicorn", "emissiongraph.api.routes:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "compute"]
