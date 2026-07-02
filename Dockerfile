# GeoSupply AI — OSINT dashboard + REST API
# Build:  docker build -t geosupply .
# Run:    docker run -p 8000:8000 -v geosupply-data:/app/data geosupply
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000

COPY requirements-osint.txt ./
RUN pip install --no-cache-dir -r requirements-osint.txt

COPY pyproject.toml README.md ./
COPY src ./src
COPY frontend ./frontend
RUN pip install --no-cache-dir --no-deps -e .

# Learning state persists in /app/data (mount a volume to keep it)
VOLUME ["/app/data"]
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=4).raise_for_status()"

CMD ["geosupply-api"]
