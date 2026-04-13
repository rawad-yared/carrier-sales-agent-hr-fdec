output "app_url" {
  description = "Public HTTPS URL for the dashboard."
  value       = "https://${var.domain_name}"
}

output "api_health_url" {
  description = "Public HTTPS URL for the API healthcheck."
  value       = "https://${var.domain_name}/api/health"
}

output "alb_dns_name" {
  description = "ALB DNS name (direct, bypasses custom domain)."
  value       = module.alb.alb_dns_name
}

output "api_repository_url" {
  description = "ECR URL for the API image — push with docker."
  value       = module.ecr.api_repository_url
}

output "dashboard_repository_url" {
  description = "ECR URL for the dashboard image — push with docker."
  value       = module.ecr.dashboard_repository_url
}

output "db_endpoint" {
  description = "RDS Postgres endpoint (hostname)."
  value       = module.rds.endpoint
}
