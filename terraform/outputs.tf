output "alb_dns_name" {
  description = "The DNS name of the ALB"
  value       = aws_lb.main.dns_name
}

output "nameservers" {
  description = "Route53 Nameservers for the domain"
  value       = data.aws_route53_zone.main.name_servers
}

output "ecr_repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}
