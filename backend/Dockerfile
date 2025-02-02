# Use official Python image as base
FROM python:3.10

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app
RUN mkdir -p /app/logs

COPY requirements.txt .
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Django
EXPOSE 8000

# Run Django development server
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "propkhoj.wsgi:application"]
