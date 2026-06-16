variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "arborwatch"
}

variable "environment" {
  description = "Environment name (e.g., prod, staging)"
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "Domain name for the application (e.g., arborwatch.net)"
  type        = string
  default     = "arborwatch.net"
}

# -----------------------------------------------------------------------------
# Database Variables
# -----------------------------------------------------------------------------
variable "db_password" {
  description = "Password for the RDS database"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.small" # t3.small is minimum for PostGIS
}

# -----------------------------------------------------------------------------
# ECS Variables
# -----------------------------------------------------------------------------
variable "web_task_cpu" {
  description = "CPU units for the web task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "web_task_memory" {
  description = "Memory for the web task in MB"
  type        = number
  default     = 1024
}

variable "worker_task_cpu" {
  description = "CPU units for the Celery worker task"
  type        = number
  default     = 1024
}

variable "worker_task_memory" {
  description = "Memory for the Celery worker task in MB"
  type        = number
  default     = 2048
}

variable "django_secret_key" {
  description = "Django SECRET_KEY"
  type        = string
  sensitive   = true
}

variable "django_superuser_username" {
  description = "Django Superuser Username"
  type        = string
  default     = ""
}

variable "django_superuser_password" {
  description = "Django Superuser Password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gfw_api_key" {
  description = "Global Forest Watch API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "noaa_cdo_token" {
  description = "NOAA CDO API Token"
  type        = string
  sensitive   = true
  default     = ""
}
