#!/usr/bin/env bash
# Build the api and dashboard images and push them to ECR, then force a new
# ECS deployment so the services pull :latest.
#
# Requires: terraform apply to have run first (creates the ECR repos + ECS services).
#
# Usage: AWS_PROFILE=carrier-sales scripts/build-and-push.sh
set -euo pipefail

: "${AWS_PROFILE:=carrier-sales}"
export AWS_PROFILE

REGION="${AWS_REGION:-us-east-1}"
CLUSTER="carrier-sales-cluster"
API_SERVICE="carrier-sales-api"
DASH_SERVICE="carrier-sales-dashboard"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
API_REPO="${REGISTRY}/carrier-sales-api"
DASH_REPO="${REGISTRY}/carrier-sales-dashboard"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

echo "→ ECR login"
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

echo "→ building api image (linux/amd64 for Fargate)"
docker buildx build \
  --platform linux/amd64 \
  --tag "${API_REPO}:latest" \
  --file api/Dockerfile \
  --push \
  .

echo "→ building dashboard image (linux/amd64 for Fargate)"
docker buildx build \
  --platform linux/amd64 \
  --tag "${DASH_REPO}:latest" \
  --file dashboard/Dockerfile \
  --push \
  dashboard

echo "→ forcing new deployment on api service"
aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${API_SERVICE}" \
  --force-new-deployment \
  --region "${REGION}" >/dev/null

echo "→ forcing new deployment on dashboard service"
aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${DASH_SERVICE}" \
  --force-new-deployment \
  --region "${REGION}" >/dev/null

echo
echo "✓ pushed and redeployed"
echo "  watch service status: aws ecs describe-services --cluster ${CLUSTER} --services ${API_SERVICE} ${DASH_SERVICE} --region ${REGION} --query 'services[*].[serviceName,runningCount,desiredCount,deployments[0].rolloutState]' --output table"
