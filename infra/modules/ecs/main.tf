resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

# ---- CloudWatch log groups ----
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name_prefix}-api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "dashboard" {
  name              = "/ecs/${var.name_prefix}-dashboard"
  retention_in_days = 30
}

# ---- IAM: task execution role (Fargate assumes this) ----
data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${var.name_prefix}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution_amazon" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow task execution role to read our Secrets Manager entries for env injection
data "aws_iam_policy_document" "task_secrets_read" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      var.api_key_secret_arn,
      var.fmcsa_webkey_secret_arn,
      var.db_password_secret_arn,
    ]
  }
}

resource "aws_iam_policy" "task_secrets_read" {
  name   = "${var.name_prefix}-task-secrets-read"
  policy = data.aws_iam_policy_document.task_secrets_read.json
}

resource "aws_iam_role_policy_attachment" "task_secrets_read" {
  role       = aws_iam_role.task_execution.name
  policy_arn = aws_iam_policy.task_secrets_read.arn
}

# ---- IAM: task role (the app's AWS identity at runtime — nothing needed for PoC) ----
resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

# ---- API task definition ----
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.api_image_uri
    essential = true
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "DB_HOST", value = var.db_endpoint },
      { name = "DB_PORT", value = "5432" },
      { name = "DB_NAME", value = var.db_name },
      { name = "DB_USER", value = var.db_username },
      { name = "LOADS_JSON_PATH", value = "/app/data/loads.json" },
    ]
    secrets = [
      { name = "API_KEY", valueFrom = var.api_key_secret_arn },
      { name = "FMCSA_WEBKEY", valueFrom = var.fmcsa_webkey_secret_arn },
      { name = "DB_PASSWORD", valueFrom = var.db_password_secret_arn },
    ]
    # entrypoint.sh builds DATABASE_URL from DB_* components at container start,
    # injecting DB_PASSWORD from Secrets Manager.
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# ---- Dashboard task definition ----
resource "aws_ecs_task_definition" "dashboard" {
  family                   = "${var.name_prefix}-dashboard"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.dashboard_cpu
  memory                   = var.dashboard_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "dashboard"
    image     = var.dashboard_image_uri
    essential = true
    portMappings = [{
      containerPort = 8501
      protocol      = "tcp"
    }]
    environment = [
      { name = "API_BASE_URL", value = "http://${var.name_prefix}-api.${var.name_prefix}.local:8000" },
    ]
    secrets = [
      { name = "DASHBOARD_API_KEY", valueFrom = var.api_key_secret_arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.dashboard.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "dashboard"
      }
    }
  }])
}

# ---- Service Discovery (so dashboard can reach the api by DNS inside the VPC) ----
resource "aws_service_discovery_private_dns_namespace" "this" {
  name        = "${var.name_prefix}.local"
  description = "Private namespace for ${var.name_prefix} services"
  vpc         = var.vpc_id
}

resource "aws_service_discovery_service" "api" {
  name = "${var.name_prefix}-api"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.this.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# ---- Services ----
resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.service_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.api.arn
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [aws_iam_role_policy_attachment.task_execution_amazon]
}

resource "aws_ecs_service" "dashboard" {
  name            = "${var.name_prefix}-dashboard"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.service_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.dashboard_target_group_arn
    container_name   = "dashboard"
    container_port   = 8501
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [
    aws_iam_role_policy_attachment.task_execution_amazon,
    aws_ecs_service.api,
  ]
}
