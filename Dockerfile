FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY resolver/ resolver/
COPY config/routes.example.yaml config/routes.yaml

ENV CONFIG_PATH=/app/config/routes.yaml

EXPOSE 8080

CMD ["uvicorn", "resolver.app:app", "--host", "0.0.0.0", "--port", "8080"]
