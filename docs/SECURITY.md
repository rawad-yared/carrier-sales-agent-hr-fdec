# Security

PoC-grade security. Threat-modeled for "demo to a prospect," not "production for a Fortune 500." Explicit about what's in and out of scope so we can defend it in the pitch.

## In scope

### HTTPS everywhere
- Custom domain, ACM-issued TLS cert, HTTPS-only listener on the ALB
- HTTP → HTTPS redirect at the ALB
- No local HTTP fallback in prod
- Locally: `uvicorn` can serve plain HTTP; `docker-compose` does too. Production is HTTPS only.

### API key authentication
- Single `X-API-Key` header on all endpoints except `/health`
- Key lives in AWS Secrets Manager, injected into ECS task as env var via task role (never in the image, never in Terraform state files outside of secret references)
- Verified by FastAPI middleware — constant-time comparison (`secrets.compare_digest`)
- Missing or wrong key → `401`, no information leak about why
- Key rotation: update Secrets Manager → force new ECS deployment → HappyRobot workflow updated with new key. Documented in `INFRA.md`.

### Secrets management
- **Never in git.** `.gitignore` covers `.env`, `*.pem`, `terraform.tfstate*`.
- **Never in the image.** Dockerfile does not `COPY` any `.env`.
- **Never logged.** Structured logger has a redactor for `Authorization`, `X-API-Key`, and anything FMCSA-flavored.
- Locally: `.env` file, gitignored, template in `.env.example`.
- Production: AWS Secrets Manager, one secret per value (`API_KEY`, `FMCSA_WEBKEY`, `DB_PASSWORD`).

### Input validation
- Every endpoint uses Pydantic models — unknown fields rejected, types enforced
- MC number validated against a regex (`^\d{1,8}$`) before hitting FMCSA
- Offer amounts validated non-negative, rounded to 2 decimals

### SQL injection
- All DB access via SQLAlchemy ORM or parameterized queries. No string-interpolated SQL anywhere.

### CORS
- Dashboard and API served from the same domain → no CORS needed in prod
- Locally: dashboard may run on a different port → permissive CORS in dev only, locked down in prod

### Logging
- Structured JSON logs to CloudWatch
- Every request gets a `request_id` (UUID), included in response header `X-Request-ID` and all log lines
- No secrets, no full credit-card-style PII in logs
- MC numbers are logged (they're public business identifiers, not PII)

## Out of scope (state clearly, defend in pitch)

- **Dashboard authentication.** PoC uses IP allowlist at the ALB or a shared basic-auth password. Real multi-user SSO would be phase 2. *Pitch framing: "production would integrate with your broker's existing IdP — Okta, Google Workspace, whatever you're on."*
- **RBAC / multi-tenant.** Single broker, single namespace. Pitch phase 2.
- **DDoS protection.** Relying on ALB + AWS shield default. No WAF rules. Fine for a demo.
- **Audit logging for compliance (SOC 2, etc.).** CloudWatch logs exist; nothing formal.
- **Encryption at rest beyond AWS defaults.** RDS uses default KMS-managed encryption. Secrets Manager is encrypted. No customer-managed keys.
- **Penetration testing.** Not in scope for PoC.
- **Rate limiting beyond a per-IP memory limiter.** Real rate limiting requires Redis or similar; out of scope.

## Threat model summary

| Threat | Mitigation | Residual |
|---|---|---|
| Attacker discovers endpoint, hits it without key | API key required, `401` | None meaningful |
| Attacker steals API key (e.g. from HappyRobot compromise) | Key rotation procedure | Depends on detection time |
| Malicious carrier submits garbage in MC number | Regex + FMCSA will reject | None |
| SQL injection via search criteria | Parameterized queries / ORM | None |
| Secrets leak in container image | Secrets via task role, not baked in | None |
| TLS downgrade | HTTPS-only listener, HSTS header | None |
| Dashboard data exposed | ALB IP allowlist (or shared basic auth) | IP list management |

## Deploy-time security checklist

- [ ] `terraform.tfstate` is in a private, encrypted S3 backend (not local, not in git)
- [ ] Secrets Manager ARNs referenced in Terraform, not secret *values*
- [ ] RDS is in a private subnet, only ECS SG can reach it
- [ ] ALB security group allows 443 from anywhere, 80 only to redirect
- [ ] ECS tasks are in private subnets with NAT egress
- [ ] No SSH anywhere. ECS Exec if debugging needed, disabled by default.
- [ ] CloudWatch log groups have retention set (30d is fine for PoC, keeps cost sane)
