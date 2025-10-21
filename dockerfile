# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED 1

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Command to run the application using Gunicorn
# Gunicorn will serve the 'app' instance found in 'app.py' (or run.py, depending on your naming)
# IMPORTANT: Since your Flask file is named 'app.py' in the previous context, we use 'app:app'.
# If you renamed it to 'run.py', you would change this to 'run:app'.
# Based on the previous session's context, your main file is 'app.py'.
CMD gunicorn --bind 0.0.0.0:$PORT app:app