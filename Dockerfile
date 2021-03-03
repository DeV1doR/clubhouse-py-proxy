FROM python:3.9

ARG BUILD_LOCAL

# Create app directory
RUN mkdir -p /app
WORKDIR /app

# Install requirements
COPY requirements.txt /app
RUN pip install -r /app/requirements.txt

# Copy app
COPY . /app
