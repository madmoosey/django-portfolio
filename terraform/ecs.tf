# ECR Repository
resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}

# -----------------------------------------------------------------------------
# Common Container Definition Locals
# -----------------------------------------------------------------------------
locals {
  common_environment = [
    { name = "DJANGO_SETTINGS_MODULE", value = "config.settings.production" },
    { name = "DJANGO_SECRET_KEY", value = var.django_secret_key },
    { name = "DJANGO_ALLOWED_HOSTS", value = "api.${var.domain_name},${var.domain_name},${aws_lb.main.dns_name},localhost,127.0.0.1" },
    { name = "CORS_ALLOWED_ORIGINS", value = "https://${var.domain_name}" },
    { name = "POSTGRES_DB", value = "arborwatch" },
    { name = "POSTGRES_USER", value = "arborwatch" },
    { name = "POSTGRES_PASSWORD", value = var.db_password },
    { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
    { name = "POSTGRES_PORT", value = "5432" },
    { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
    { name = "CELERY_BROKER_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/1" },
    { name = "AWS_STORAGE_BUCKET_NAME", value = aws_s3_bucket.media.bucket },
    { name = "GFW_API_KEY", value = var.gfw_api_key },
    { name = "NOAA_CDO_TOKEN", value = var.noaa_cdo_token },
    { name = "DJANGO_SUPERUSER_USERNAME", value = var.django_superuser_username },
    { name = "DJANGO_SUPERUSER_PASSWORD", value = var.django_superuser_password }
  ]
}

# -----------------------------------------------------------------------------
# Web Task & Service
# -----------------------------------------------------------------------------
resource "aws_ecs_task_definition" "web" {
  family                   = "${var.project_name}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.web_task_cpu
  memory                   = var.web_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name      = "web"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = local.common_environment
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "web"
      }
    }
  }])
}

resource "aws_ecs_service" "web" {
  name            = "${var.project_name}-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
}

# -----------------------------------------------------------------------------
# Celery Worker Task & Service
# -----------------------------------------------------------------------------
resource "aws_ecs_task_definition" "celery_worker" {
  family                   = "${var.project_name}-celery-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_task_cpu
  memory                   = var.worker_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name      = "celery-worker"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true
    command   = ["celery", "-A", "config", "worker", "--loglevel=info", "--concurrency=2", "--queues=default,ingest,weather,analysis"]
    environment = concat(local.common_environment, [
      { name = "SKIP_COLLECTSTATIC", value = "true" }
    ])
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "celery-worker"
      }
    }
  }])
}

resource "aws_ecs_service" "celery_worker" {
  name            = "${var.project_name}-celery-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery_worker.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
}

# -----------------------------------------------------------------------------
# Celery Beat Task & Service
# -----------------------------------------------------------------------------
resource "aws_ecs_task_definition" "celery_beat" {
  family                   = "${var.project_name}-celery-beat"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name      = "celery-beat"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true
    command   = ["celery", "-A", "config", "beat", "--loglevel=info", "--scheduler=django_celery_beat.schedulers:DatabaseScheduler"]
    environment = concat(local.common_environment, [
      { name = "SKIP_COLLECTSTATIC", value = "true" }
    ])
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "celery-beat"
      }
    }
  }])
}

resource "aws_ecs_service" "celery_beat" {
  name            = "${var.project_name}-celery-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery_beat.arn
  desired_count   = 1 # IMPORTANT: Beat must only have 1 instance
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
}
