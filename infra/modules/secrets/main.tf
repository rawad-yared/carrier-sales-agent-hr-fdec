terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

resource "random_password" "api_key" {
  length  = 48
  special = false
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "api_key" {
  name                    = "${var.name_prefix}/api-key"
  description             = "Shared X-API-Key for the carrier sales backend"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = random_password.api_key.result
}

resource "aws_secretsmanager_secret" "fmcsa_webkey" {
  name                    = "${var.name_prefix}/fmcsa-webkey"
  description             = "FMCSA QCMobile API webKey"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "fmcsa_webkey" {
  secret_id     = aws_secretsmanager_secret.fmcsa_webkey.id
  secret_string = var.fmcsa_webkey
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.name_prefix}/db-password"
  description             = "RDS Postgres master password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}
