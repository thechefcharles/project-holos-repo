FROM python:3.12-slim

WORKDIR /app

# Install git and git-lfs
RUN apt-get update && apt-get install -y git git-lfs curl && apt-get clean

# Initialize git-lfs
RUN git lfs install --skip-repo

# Copy repo (files will be LFS pointers initially)
COPY . /app/

# Pull LFS files
RUN git lfs pull origin || true

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8080

# Run Flask app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "holos_tools.serve_api:app"]
