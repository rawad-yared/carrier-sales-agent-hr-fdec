variable "project" {
  description = "Short project identifier — used as a name prefix on all resources."
  type        = string
  default     = "carrier-sales"
}

variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "domain_name" {
  description = "Registered apex domain for the dashboard + API."
  type        = string
  default     = "carrier-sales-demo.com"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "AZs to spread subnets across. 2 is the minimum for ALB + RDS."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "db_name" {
  description = "Postgres database name."
  type        = string
  default     = "carrier_sales"
}

variable "db_username" {
  description = "Postgres master username."
  type        = string
  default     = "carrier"
}

variable "api_cpu" {
  description = "API task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "API task memory in MiB."
  type        = number
  default     = 512
}

variable "dashboard_cpu" {
  description = "Dashboard task CPU units."
  type        = number
  default     = 256
}

variable "dashboard_memory" {
  description = "Dashboard task memory in MiB."
  type        = number
  default     = 512
}

variable "fmcsa_webkey" {
  description = "FMCSA QCMobile API key. Set via `export TF_VAR_fmcsa_webkey=...` before running terraform."
  type        = string
  sensitive   = true
}
