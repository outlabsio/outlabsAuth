# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install uv, a very fast Python package installer
RUN pip install uv

# Copy the project definition file
COPY pyproject.toml ./

# Install project dependencies using uv
# Using --system to install into the global site-packages of the container's Python
RUN uv pip install --system --no-cache --requirement pyproject.toml

# Copy the rest of the application's code into the container at /app
# This is done after installing dependencies to leverage Docker's layer caching.
COPY . /app

# Command to run the application
# The command is specified in docker-compose.yml to allow for hot-reloading 