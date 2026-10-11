FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY src/backend/requirements.txt src/backend/requirements.txt
RUN pip install --no-cache-dir -r src/backend/requirements.txt

COPY aegra.json .
COPY data/ data/
COPY datasets/ datasets/
COPY src/ src/

EXPOSE 8000
# Default: Aegra serves our REST API (/api/v1) and the Agent Protocol graph `agent` (needs Postgres).
# SERVER=uvicorn runs only the REST API (no Postgres needed), e.g. as a fallback in a demo.
ENV SERVER=aegra HOST=0.0.0.0 PORT=8000 AEGRA_CONFIG=aegra.json
CMD ["sh", "-c", "if [ \"$SERVER\" = uvicorn ]; then unset AEGRA_CONFIG; exec uvicorn backend.main:app --host 0.0.0.0 --port 8000; else exec aegra serve; fi"]
