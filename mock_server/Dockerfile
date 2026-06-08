FROM python:3.14-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the package under /app/mock_server so `mock_server.*` imports resolve.
COPY . /app/mock_server
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "mock_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
