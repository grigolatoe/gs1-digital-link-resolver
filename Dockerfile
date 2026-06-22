FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/grigolatoe/gs1-digital-link-resolver"
LABEL org.opencontainers.image.description="Open-source GS1 Digital Link resolver for EU Digital Product Passports"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.version="1.0.0"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY resolver/ resolver/
COPY profiles/ profiles/
COPY config/routes.example.yaml config/routes.yaml

ENV CONFIG_PATH=/app/config/routes.yaml

EXPOSE 8080

CMD ["uvicorn", "resolver.app:app", "--host", "0.0.0.0", "--port", "8080"]
