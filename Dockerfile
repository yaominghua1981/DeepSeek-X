FROM python:3.11-slim

# Set image label
LABEL name="deepseek-x"

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/venv/bin:$PATH" \
    HTTP_PROXY=http://host.docker.internal:8118 \
    HTTPS_PROXY=http://host.docker.internal:8118 \
    NO_PROXY=localhost,127.0.0.1

# Install system dependencies including curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /app/venv

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.2 \
    uvicorn==0.27.1 \
    pydantic==2.6.1 \
    httpx==0.26.0 \
    python-dotenv==1.0.1 \
    aiohttp==3.9.3 \
    sse-starlette==1.8.2

# Copy project files
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 