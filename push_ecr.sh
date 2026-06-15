#!/bin/bash
set -e

# Extract AWS keys from .env
AWS_ACCESS_KEY_ID=$(grep '^AWS_ACCESS_KEY=' .env | cut -d '=' -f 2)
AWS_SECRET_ACCESS_KEY=$(grep '^AWS_SECRET_KEY=' .env | cut -d '=' -f 2)

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY
export AWS_DEFAULT_REGION="us-east-1"
ACCOUNT_ID="452112380264"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"

echo "Getting ECR login password..."
# Use dockerized AWS CLI to get the password and pipe to docker login
docker run --rm -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" -e AWS_DEFAULT_REGION="us-east-1" amazon/aws-cli ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

echo "Building Docker image..."
docker build -t arborwatch .

echo "Tagging and pushing image to ECR..."
docker tag arborwatch:latest $ECR_REGISTRY/arborwatch:latest
docker push $ECR_REGISTRY/arborwatch:latest

echo "Force updating ECS services to use new image..."
docker run --rm -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" -e AWS_DEFAULT_REGION="us-east-1" amazon/aws-cli ecs update-service --cluster arborwatch-cluster --service arborwatch-web --force-new-deployment
docker run --rm -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" -e AWS_DEFAULT_REGION="us-east-1" amazon/aws-cli ecs update-service --cluster arborwatch-cluster --service arborwatch-celery-worker --force-new-deployment
docker run --rm -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" -e AWS_DEFAULT_REGION="us-east-1" amazon/aws-cli ecs update-service --cluster arborwatch-cluster --service arborwatch-celery-beat --force-new-deployment

echo "Done!"
