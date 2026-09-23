# Use a small official Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependencies first for better Docker caching
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend package and tests
COPY backend ./backend
COPY data/documents ./data/documents
COPY tests ./tests

# Start the FastAPI server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]