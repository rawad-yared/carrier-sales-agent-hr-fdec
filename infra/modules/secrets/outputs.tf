output "api_key_secret_arn" {
  value = aws_secretsmanager_secret.api_key.arn
}

output "fmcsa_webkey_secret_arn" {
  value = aws_secretsmanager_secret.fmcsa_webkey.arn
}

output "db_password_secret_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}

# Passed in-memory to the RDS module so Terraform can set the master password
# without the user having to populate Secrets Manager manually.
output "db_password_value" {
  value     = random_password.db_password.result
  sensitive = true
}
