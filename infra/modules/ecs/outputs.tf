output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "dashboard_service_name" {
  value = aws_ecs_service.dashboard.name
}
