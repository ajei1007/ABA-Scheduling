# Use an official Python runtime as the base image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /var/task

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies (including matplotlib) into the container
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

# Expose port 80 for the application
EXPOSE 80


# Set environment variable for Flask development mode
ENV FLASK_ENV=development
ENV FLASK_APP=app2.py

# Define the command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=80", "--reload"]
