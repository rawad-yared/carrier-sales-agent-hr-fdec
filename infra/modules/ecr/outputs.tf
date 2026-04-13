output "api_repository_url" {
  value = aws_ecr_repository.this["api"].repository_url
}

output "dashboard_repository_url" {
  value = aws_ecr_repository.this["dashboard"].repository_url
}

output "api_repository_name" {
  value = aws_ecr_repository.this["api"].name
}

output "dashboard_repository_name" {
  value = aws_ecr_repository.this["dashboard"].name
}
