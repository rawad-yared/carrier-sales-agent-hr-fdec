# Deliverables Checklist

The six things we owe HappyRobot. Track status here as we ship.

| # | Deliverable | Location | Status |
|---|---|---|---|
| 1 | Email to Carlos Becker (c.becker@happyrobot.ai, recruiter in CC) | `deliverables/email.md` | ✅ drafted — user sends |
| 2 | Build description doc for "Acme Logistics" | `deliverables/acme-logistics-proposal.md` | ✅ drafted (324 lines) |
| 3 | Deployed dashboard URL | `https://carrier-sales-demo.com/` | ✅ live (HTTPS + ACM + ALB) |
| 4 | Code repo link | This repo (paste URL when published) | ⬜ user publishes |
| 5 | HappyRobot workflow link | `docs/HAPPYROBOT.md` bottom | ✅ workflow built, live, wired to production API — user pastes share link |
| 6 | 5-min video (setup, demo, dashboard) | `deliverables/video.md` | ✅ script finalized — user records |

## Additional considerations covered

| Requirement | How we meet it |
|---|---|
| HTTPS | ACM cert + ALB, HTTPS-only listener |
| API key auth on all endpoints | Middleware, Secrets Manager-backed |
| Deployed to cloud | AWS ECS Fargate |
| Reproducible deploy | Terraform + documented runbook in `INFRA.md` |
| Web call trigger (no phone number) | HappyRobot web call config |
| Docker containerization | Two Dockerfiles, docker-compose for local |

## Pre-submission checklist

- [ ] All six deliverables present and linked
- [ ] Dashboard URL loads over HTTPS
- [ ] `/health` returns 200 from the deployed API
- [ ] HappyRobot workflow can complete a full happy-path call end-to-end
- [ ] A negotiation actually triggers on the demo call
- [ ] Dashboard shows the demo call within 30 seconds
- [ ] Email drafted, reviewed by user, sent
- [ ] Acme Logistics doc reviewed by user
- [ ] Video recorded and linked
- [ ] Repo is public (or access shared with reviewers)
- [ ] README front-loads everything a reviewer needs
