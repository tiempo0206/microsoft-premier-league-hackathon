# Build context: matchmind/. Role B backend only; no frontend build or AI implementation.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 MATCHMIND_SERVE_FRONTEND=0
WORKDIR /app
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && useradd --uid 10001 --create-home app
# Allowlisted sources: no .env, local venv, node_modules or classroom resources.
COPY backend/*.py ./backend/
COPY contracts/*.py contracts/*.json contracts/VERSION ./contracts/
COPY data/fixtures ./data/fixtures
COPY data/extra/validated-demo ./data/extra/validated-demo
COPY data/generator/*.py ./data/generator/
COPY deploy/__init__.py deploy/preflight.py ./deploy/
USER app
RUN python -m deploy.preflight
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health',timeout=3)"
CMD ["python", "-m", "backend.run"]
