variable "name_prefix" {
  type = string
}

variable "fmcsa_webkey" {
  description = "FMCSA QCMobile API key. Set via TF_VAR_fmcsa_webkey when running terraform."
  type        = string
  sensitive   = true
}
