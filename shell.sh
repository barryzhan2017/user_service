#!/usr/bin/env bash

# Build the docker and give it a name
docker build -t user_service .


# Run the container locally
docker run -p 80:80 user_service

# Login ECS
aws ecr get-login-password \
    --region us-east-2 \
| docker login \
  --username AWS \
  --password-stdin 226082231735.dkr.ecr.us-east-2.amazonaws.com

# Tag my image with the repo to use
docker tag user_service 226082231735.dkr.ecr.us-east-2.amazonaws.com/user-service:user_service

# Push to the repo
docker push 226082231735.dkr.ecr.us-east-2.amazonaws.com/user-service