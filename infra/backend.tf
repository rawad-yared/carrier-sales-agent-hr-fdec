terraform {
  backend "s3" {
    bucket         = "carrier-sales-hr-fdec-tfstate-559307249592"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "carrier-sales-hr-fdec-tfstate-lock"
    encrypt        = true
  }
}
