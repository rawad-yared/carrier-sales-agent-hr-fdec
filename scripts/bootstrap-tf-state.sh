#!/usr/bin/env bash
# Bootstrap the S3 bucket + DynamoDB table that hold Terraform state.
# Idempotent: safe to rerun. Must be run once before `terraform init`.
#
# Usage: AWS_PROFILE=carrier-sales scripts/bootstrap-tf-state.sh
set -euo pipefail

: "${AWS_PROFILE:=carrier-sales}"
export AWS_PROFILE

REGION="${AWS_REGION:-us-east-1}"
PROJECT="carrier-sales-hr-fdec"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="${PROJECT}-tfstate-${ACCOUNT_ID}"
TABLE="${PROJECT}-tfstate-lock"

echo "→ account: ${ACCOUNT_ID}"
echo "→ region:  ${REGION}"
echo "→ bucket:  ${BUCKET}"
echo "→ table:   ${TABLE}"
echo

# ---- S3 bucket ----
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "✓ bucket ${BUCKET} already exists"
else
  echo "→ creating bucket ${BUCKET}"
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket \
      --bucket "${BUCKET}" \
      --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}"
  fi
fi

echo "→ enabling versioning"
aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

echo "→ enabling server-side encryption (AES256)"
aws s3api put-bucket-encryption \
  --bucket "${BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
    }]
  }'

echo "→ blocking public access"
aws s3api put-public-access-block \
  --bucket "${BUCKET}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# ---- DynamoDB lock table ----
if aws dynamodb describe-table --table-name "${TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "✓ lock table ${TABLE} already exists"
else
  echo "→ creating lock table ${TABLE}"
  aws dynamodb create-table \
    --table-name "${TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" >/dev/null
  echo "→ waiting for table to become ACTIVE"
  aws dynamodb wait table-exists --table-name "${TABLE}" --region "${REGION}"
fi

echo
echo "✓ bootstrap complete"
echo
echo "Put these in infra/backend.tf:"
cat <<HCL
  backend "s3" {
    bucket         = "${BUCKET}"
    key            = "terraform.tfstate"
    region         = "${REGION}"
    dynamodb_table = "${TABLE}"
    encrypt        = true
  }
HCL
