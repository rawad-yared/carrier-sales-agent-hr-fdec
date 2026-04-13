locals {
  name_prefix = var.project
  common_tags = {
    Project = var.project
  }
}

module "network" {
  source = "./modules/network"

  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  azs         = var.azs
}

module "ecr" {
  source = "./modules/ecr"

  name_prefix = local.name_prefix
}

module "secrets" {
  source = "./modules/secrets"

  name_prefix  = local.name_prefix
  fmcsa_webkey = var.fmcsa_webkey
}

# ECS service SG lives at the root to break the dependency cycle between
# the rds module (wants ECS SG for its ingress rule) and the ecs module
# (wants RDS endpoint for its task env).
resource "aws_security_group" "ecs_service" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "ECS service SG - allow app ports from ALB only"
  vpc_id      = module.network.vpc_id

  ingress {
    description     = "api from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [module.alb.alb_security_group_id]
  }

  ingress {
    description     = "dashboard from ALB"
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [module.alb.alb_security_group_id]
  }

  ingress {
    description = "api from sibling ECS tasks (dashboard calls api via service discovery)"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-ecs-sg"
  }
}

module "rds" {
  source = "./modules/rds"

  name_prefix            = local.name_prefix
  vpc_id                 = module.network.vpc_id
  private_subnet_ids     = module.network.private_subnet_ids
  ecs_security_group_id  = aws_security_group.ecs_service.id
  db_name                = var.db_name
  db_username            = var.db_username
  db_password_secret_arn = module.secrets.db_password_secret_arn
  db_password_value      = module.secrets.db_password_value
}

module "dns" {
  source = "./modules/dns"

  domain_name        = var.domain_name
  alb_dns_name       = module.alb.alb_dns_name
  alb_zone_id        = module.alb.alb_zone_id
}

module "alb" {
  source = "./modules/alb"

  name_prefix       = local.name_prefix
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  certificate_arn   = module.dns.certificate_arn
}

module "ecs" {
  source = "./modules/ecs"

  name_prefix              = local.name_prefix
  region                   = var.region
  vpc_id                   = module.network.vpc_id
  private_subnet_ids       = module.network.private_subnet_ids
  service_security_group_id = aws_security_group.ecs_service.id

  api_target_group_arn       = module.alb.api_target_group_arn
  dashboard_target_group_arn = module.alb.dashboard_target_group_arn

  api_image_uri       = "${module.ecr.api_repository_url}:latest"
  dashboard_image_uri = "${module.ecr.dashboard_repository_url}:latest"

  api_cpu          = var.api_cpu
  api_memory       = var.api_memory
  dashboard_cpu    = var.dashboard_cpu
  dashboard_memory = var.dashboard_memory

  db_endpoint = module.rds.endpoint
  db_name     = var.db_name
  db_username = var.db_username

  api_key_secret_arn       = module.secrets.api_key_secret_arn
  fmcsa_webkey_secret_arn  = module.secrets.fmcsa_webkey_secret_arn
  db_password_secret_arn   = module.secrets.db_password_secret_arn
}
