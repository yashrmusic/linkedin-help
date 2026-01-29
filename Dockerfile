FROM python:3.10-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements (if you have them, otherwise we install manually for now)
COPY . .

# Install Python dependencies
RUN pip install fastapi uvicorn playwright playwright-stealth pyyaml

# Install Playwright browsers (Chromium only to save space)
RUN playwright install chromium
RUN playwright install-deps chromium

# Expose the dashboard port
EXPOSE 8001

# Run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
