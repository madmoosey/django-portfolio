resource "aws_db_subnet_group" "rds" {
  name       = "${var.project_name}-rds-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_db_instance" "postgres" {
  identifier        = "${var.project_name}-db"
  engine            = "postgres"
  engine_version    = "16" # Match local PostGIS 16
  instance_class    = var.db_instance_class
  allocated_storage = 20
  
  db_name  = "arborwatch"
  username = "arborwatch"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.rds.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  multi_az               = false # Set to true for production high availability
  publicly_accessible    = false
  skip_final_snapshot    = true
  
  # Allow minor version upgrades
  auto_minor_version_upgrade = true
}
