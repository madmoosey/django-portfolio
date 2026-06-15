#!/bin/bash

# Extract AWS keys and secrets from .env
AWS_ACCESS_KEY_ID=$(grep '^AWS_ACCESS_KEY=' .env | cut -d '=' -f 2)
AWS_SECRET_ACCESS_KEY=$(grep '^AWS_SECRET_KEY=' .env | cut -d '=' -f 2)
POSTGRES_PASSWORD=$(grep '^POSTGRES_PASSWORD=' .env | cut -d '=' -f 2)
DJANGO_SECRET_KEY=$(grep '^DJANGO_SECRET_KEY=' .env | cut -d '=' -f 2)
GFW_API_KEY=$(grep '^GFW_API_KEY=' .env | cut -d '=' -f 2 | tr -d '"')
NOAA_CDO_TOKEN=$(grep '^NOAA_CDO_TOKEN=' .env | cut -d '=' -f 2 | tr -d '"')

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY

# Use docker to run terraform
docker run --rm -v $(pwd):/workspace -w /workspace \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e TF_VAR_db_password="$POSTGRES_PASSWORD" \
  -e TF_VAR_django_secret_key="$DJANGO_SECRET_KEY" \
  -e TF_VAR_gfw_api_key="$GFW_API_KEY" \
  -e TF_VAR_noaa_cdo_token="$NOAA_CDO_TOKEN" \
  hashicorp/terraform:latest "$@"
