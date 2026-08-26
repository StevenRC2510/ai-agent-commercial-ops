FROM python:3.11-slim

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pytest.ini ./
COPY pyproject.toml ./
COPY app ./app
COPY tests ./tests

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app"]
