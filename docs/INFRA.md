# Infrastructure (AWS + Terraform)

> **Status: skeleton.** Fill in as we build. Claude Code can start scaffolding the Terraform modules from the structure below.

## Target architecture

See `ARCHITECTURE.md` for the diagram. Components to provision:

- VPC with public + private subnets across 2 AZs
- ALB in public subnets, security group: 443 from `0.0.0.0/0`, 80 redirect only
- ACM cert for the custom domain (DNS validation via Route 53)
- Route 53 A-record pointing to the ALB
- ECS cluster (Fargate)
- 2 ECS services: `api` and `dashboard`
- ECS task definitions reference images in ECR
- ECR repositories: `carrier-sales-agent-hr-fdec-api`, `carrier-sales-agent-hr-fdec-dashboard`
- RDS Postgres `db.t4g.micro`, in private subnets, SG allows 5432 from ECS SG only
- Secrets Manager secrets: `api-key`, `fmcsa-webkey`, `db-password`
- CloudWatch log groups: `/ecs/api`, `/ecs/dashboard`, 30-day retention
- IAM task role with `secretsmanager:GetSecretValue` for the three secrets
- IAM execution role (standard ECS)

## Terraform module layout

```
infra/
├── main.tf              ← providers, backend config, module wiring
├── variables.tf
├── outputs.tf
├── modules/
│   ├── network/         ← VPC, subnets, NAT, route tables
│   ├── ecs/             ← cluster, services, task defs
│   ├── alb/             ← ALB, listeners, target groups, path routing
│   ├── rds/             ← RDS instance, subnet group, SG
│   ├── ecr/             ← two repos
│   └── secrets/         ← Secrets Manager entries (values pulled from vars)
└── environments/
    └── prod.tfvars      ← domain name, DB sizing, etc.
```

## State backend

S3 + DynamoDB lock. Bucket name: `carrier-sales-agent-hr-fdec-tfstate-<random>`, encrypted, versioned.

## Runbook: zero to deployed

1. Prereqs: AWS CLI configured, Terraform ≥1.6, Docker, domain in Route 53
2. Create the state S3 bucket + DynamoDB table (one-time, manual or small bootstrap TF)
3. Set secrets in Secrets Manager (values placeholder, rotated later):
   - `api-key`: generate a random 32-char string
   - `fmcsa-webkey`: your FMCSA registration key
   - `db-password`: let Terraform generate and write
4. `cd infra && terraform init && terraform apply -var-file=environments/prod.tfvars`
5. Build and push images:
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin <acct>.dkr.ecr.<region>.amazonaws.com
   docker build -t carrier-sales-agent-hr-fdec-api ./api && docker tag ... && docker push ...
   docker build -t carrier-sales-agent-hr-fdec-dashboard ./dashboard && docker tag ... && docker push ...
   ```
6. Force ECS services to pick up new images: `aws ecs update-service --force-new-deployment`
7. Verify DNS resolves, `curl https://<domain>/api/health` returns `200`

TODO: turn steps 5–6 into a shell script (`scripts/deploy.sh`).

## Cost estimate (PoC, us-east-1)

- ALB: ~$16/mo
- 2× Fargate tasks (0.25 vCPU, 0.5 GB): ~$15/mo total
- RDS t4g.micro: ~$12/mo
- Route 53 hosted zone: $0.50/mo
- Secrets Manager: ~$1.20/mo (3 secrets)
- Data transfer: negligible for demo

**Total: ~$45/mo.** Cheap enough to leave up for the demo and a few weeks after.

## Key rotation procedure

[TODO — write after first deploy]

## Disaster recovery

Out of scope for PoC. RDS has default 7-day automated backups; that's it.

## Open questions

- [ ] Custom domain: which one? (user to decide)
- [ ] Region: us-east-1 default, or closer to Carlos / broker customer?
- [ ] RDS single-AZ vs multi-AZ: single for PoC cost; revisit for real prod
