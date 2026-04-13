# Deploy runbook

One-shot Terraform deploy of the carrier sales PoC to AWS.

## What this creates

| Module | Resources |
|---|---|
| `network` | VPC (10.0.0.0/16), 2 public + 2 private subnets across 2 AZs, IGW, NAT gateway, route tables |
| `ecr` | 2 ECR repos (`carrier-sales-api`, `carrier-sales-dashboard`) with lifecycle policies |
| `secrets` | 3 Secrets Manager entries (`api-key`, `fmcsa-webkey`, `db-password`) |
| `rds` | Postgres 16 `db.t4g.micro`, 20GB gp3, single-AZ, private subnet, encrypted |
| `alb` | ALB, HTTPS listener, HTTP → HTTPS redirect, path rule `/api/*` → api TG, default → dashboard TG |
| `dns` | Route 53 A records (apex + www), ACM cert with DNS validation |
| `ecs` | Fargate cluster, task execution + task roles, task defs, 2 services, CloudWatch log groups (30d), Cloud Map service discovery |

## Estimated monthly cost (us-east-1, PoC sizing)

| Item | ~$/mo |
|---|---|
| ALB | $16 |
| Fargate (2 × 0.25 vCPU, 0.5 GB, 24/7) | $15 |
| RDS `db.t4g.micro` (single-AZ, 20 GB gp3) | $12 |
| NAT gateway (single, 24/7 + small data) | $32 |
| Secrets Manager (3 entries) | $1.20 |
| Route 53 hosted zone | $0.50 |
| ECR storage + CloudWatch logs | ~$1 |
| **Total** | **~$78/mo** |

Biggest cost contributor is the NAT gateway. Drop it (use VPC endpoints + public Fargate tasks) to save ~$32/mo for a pure PoC. Out of scope for this build.

## Prerequisites

1. AWS profile `carrier-sales` with `AdministratorAccess`, `us-east-1` region
2. Domain `carrier-sales-demo.com` registered in Route 53 with an auto-created hosted zone
3. FMCSA webkey in hand (set via env var below)
4. `terraform >= 1.6`, `docker`, `aws` CLI installed
5. Terraform state bucket bootstrapped (see Step 0)

## Step 0 — Bootstrap state (once per account)

```bash
AWS_PROFILE=carrier-sales scripts/bootstrap-tf-state.sh
```

Creates the S3 bucket and DynamoDB lock table. Idempotent. Already run for this project.

## Step 1 — Terraform init + plan

```bash
cd infra
export AWS_PROFILE=carrier-sales
export TF_VAR_fmcsa_webkey="<your-fmcsa-webkey>"

terraform init
terraform plan -out=plan.tfplan
```

Review the plan output. You should see ~40-50 resources to create and zero to destroy.

## Step 2 — Apply (real spend begins here)

```bash
terraform apply plan.tfplan
```

This takes ~8-15 minutes. The slowest resources are RDS (~6 min) and the ACM cert DNS validation (~2-5 min). The ECS services will come up but initially fail health checks because the ECR repos are still empty — that's expected, we push images next.

## Step 3 — Build and push images

```bash
cd ..
AWS_PROFILE=carrier-sales scripts/build-and-push.sh
```

Builds both Docker images for `linux/amd64` (Fargate), pushes to ECR, and forces new deployments on both ECS services. Takes ~3-5 minutes.

## Step 4 — Verify

Wait ~2 minutes for the ECS tasks to stabilize, then:

```bash
curl https://carrier-sales-demo.com/api/health
# → {"status":"ok"}

curl -H "X-API-Key: $(aws secretsmanager get-secret-value \
  --secret-id carrier-sales/api-key --query SecretString --output text \
  --profile carrier-sales)" \
  https://carrier-sales-demo.com/api/calls?limit=5
```

Open **https://carrier-sales-demo.com/** in a browser — Streamlit dashboard should load.

## Step 5 — Seed synthetic calls (optional, for demo)

```bash
API_BASE=https://carrier-sales-demo.com \
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id carrier-sales/api-key --query SecretString --output text \
  --profile carrier-sales) \
python scripts/seed_synthetic_calls.py
```

## Teardown

```bash
cd infra
terraform destroy
```

Takes ~10 minutes. RDS final snapshot is skipped (`skip_final_snapshot = true`), ECR repos use `force_delete = true`. The Route 53 hosted zone and the domain registration are NOT destroyed — they were created outside Terraform.

## Troubleshooting

**`terraform plan` fails with `InvalidClientTokenId`** — credentials aren't active yet. Wait 1 minute after creating the IAM user/key.

**ECS service stuck in `rolloutState: IN_PROGRESS`** — check the service events: `aws ecs describe-services ...`. Most common causes: image pull failure (ECR repo empty — run `build-and-push.sh`), task definition references a missing secret ARN, security group blocking DB access.

**ALB target showing `unhealthy`** — the task is running but failing the TG health check. `aws logs tail /ecs/carrier-sales-api --follow --profile carrier-sales` to see what's happening inside the container. Most common: DATABASE_URL building incorrectly, alembic migration failing.

**ACM cert stuck validating** — DNS validation records take 1-5 minutes to propagate. If it's been longer, check the hosted zone has the validation CNAME records Terraform created.
