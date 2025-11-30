FROM python:3.11-slim

# Working directory inside container
WORKDIR /app

# Install required Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 81 (Flask app runs here)
EXPOSE 81

# Run the application
CMD ["python3", "app.py"]
