variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "service_security_group_id" {
  type = string
}

variable "api_target_group_arn" {
  type = string
}

variable "dashboard_target_group_arn" {
  type = string
}

variable "api_image_uri" {
  type = string
}

variable "dashboard_image_uri" {
  type = string
}

variable "api_cpu" {
  type = number
}

variable "api_memory" {
  type = number
}

variable "dashboard_cpu" {
  type = number
}

variable "dashboard_memory" {
  type = number
}

variable "db_endpoint" {
  type = string
}

variable "db_name" {
  type = string
}

variable "db_username" {
  type = string
}

variable "api_key_secret_arn" {
  type = string
}

variable "fmcsa_webkey_secret_arn" {
  type = string
}

variable "db_password_secret_arn" {
  type = string
}
