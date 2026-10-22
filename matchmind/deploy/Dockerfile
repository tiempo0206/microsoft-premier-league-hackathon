# Build context: matchmind/. AB preview only; no live model client is installed.
FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
RUN npm install --global pnpm@11.25.0 --registry=https://registry.npmjs.org/
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --registry=https://registry.npmjs.org/
COPY contracts/types.ts /build/contracts/types.ts
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN pnpm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && useradd --uid 10001 --create-home app
# Allowlisted sources: no .env, local venv, node_modules or classroom resources.
COPY backend/*.py ./backend/
COPY contracts/*.py contracts/*.json contracts/VERSION ./contracts/
COPY contracts/examples ./contracts/examples
COPY ai/*.py ./ai/
COPY data/fixtures ./data/fixtures
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health',timeout=3)"
CMD ["python", "-m", "backend.run"]
