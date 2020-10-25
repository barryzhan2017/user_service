#!/usr/bin/env bash

# Build the docker and give it a name
docker build -t user_service .




# Run the container locally
docker run -p 80:80 user_service

