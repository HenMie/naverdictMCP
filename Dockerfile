FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Install the application and its dependencies
RUN pip install --no-cache-dir .

# Expose the port
EXPOSE 8000

# Set environment variables
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8000

# Run the server
CMD ["python", "src/server.py"]
