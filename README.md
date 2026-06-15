# ArborWatch

**US Deforestation & Severe Weather Tracking Platform**

[![CI](https://github.com/madmoosey/django-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/madmoosey/django-portfolio/actions/workflows/ci.yml)

ArborWatch ingests US deforestation data from Global Forest Watch, overlays NOAA temperature and severe weather events, and uses ML models (XGBoost) to predict county-level risk for heat waves, hurricanes, and tornadoes.

🌐 **Domain**: [arborwatch.net](https://arborwatch.net)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 5.1, Django REST Framework |
| **Database** | PostgreSQL 16 + PostGIS |
| **Task Queue** | Celery + Redis |
| **ML** | scikit-learn, XGBoost, SHAP |
| **Infrastructure** | Docker, AWS ECS Fargate, Terraform |
| **CI/CD** | GitHub Actions |

## Data Sources

- **[Global Forest Watch](https://www.globalforestwatch.org/)** — Tree cover loss & deforestation alerts
- **[NOAA NCEI](https://www.ncei.noaa.gov/)** — Historical temperature observations
- **[NOAA Storm Events](https://www.ncdc.noaa.gov/stormevents/)** — Severe weather events (1950–present)
- **[NWS API](https://api.weather.gov/)** — Real-time severe weather alerts

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Make (optional, for convenience commands)

### Setup

```bash
# Clone the repository
git clone https://github.com/madmoosey/django-portfolio.git
cd django-portfolio

# Copy environment template
cp .env.example .env

# Build and start all services
make up
# or: docker compose up -d

# Create a superuser
make superuser

# Open the app
open http://localhost:8000/api/docs/    # Swagger UI
open http://localhost:8000/api/health/  # Health check
open http://localhost:8000/admin/       # Django admin
open http://localhost:5555              # Flower (Celery monitor)
```

### Common Commands

```bash
make up          # Start all Docker services
make down        # Stop all services
make test        # Run tests
make coverage    # Run tests with coverage
make lint        # Run linters
make format      # Auto-format code
make migrate     # Run database migrations
make shell       # Open Django shell
make logs        # Follow all service logs
make clean       # Remove containers and volumes
```

## Project Structure

```
arborwatch/
├── apps/
│   ├── core/           # Custom user, BaseModel, health checks
│   ├── geodata/        # US state/county boundaries (PostGIS)
│   ├── deforestation/  # Tree cover loss data
│   ├── weather/        # Temperature observations
│   ├── storms/         # Severe weather events & alerts
│   ├── analysis/       # ML risk prediction engine
│   ├── api/            # DRF routers, versioned endpoints
│   └── ingest/         # Celery ETL tasks & API clients
├── config/
│   ├── settings/       # base.py, local.py, production.py
│   ├── celery.py       # Celery app configuration
│   ├── urls.py         # URL routing
│   └── wsgi.py         # WSGI entrypoint
├── infra/
│   └── terraform/      # AWS infrastructure as code
├── requirements/       # Dependency files
├── scripts/            # Entrypoint & deployment scripts
├── docker-compose.yml
├── Dockerfile
└── Makefile
```

## API Documentation

When running locally, API documentation is available at:
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## License

This project is a portfolio demonstration. All rights reserved.
