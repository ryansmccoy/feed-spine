# FeedSpine Deployment

Deployment configurations and infrastructure templates for FeedSpine.

## Directory Structure

```
deploy/
├── docker/                 # Docker configurations
│   ├── docker-compose.yml  # Full development stack
│   ├── docker-compose.dev.yml   # Minimal dev setup
│   ├── docker-compose.prod.yml  # Production setup
│   ├── Dockerfile          # Main FeedSpine image
│   ├── Dockerfile.api      # FastAPI service image
│   └── Dockerfile.worker   # Background worker image
├── kubernetes/             # Kubernetes manifests
│   ├── base/               # Kustomize base
│   └── overlays/           # Environment overlays
├── terraform/              # Infrastructure as code (placeholder)
└── configs/                # Configuration templates
    ├── .env.example        # Environment variables
    └── config.example.yaml # Application config
```

## Quick Start (Docker)

### Development Environment

```bash
# Start all services (Postgres, Redis, Elasticsearch)
cd deploy/docker
docker compose up -d

# Verify services
docker compose ps
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| postgres | 5432 | Storage backend |
| redis | 6379 | Cache and queue |
| elasticsearch | 9200 | Search backend |
| feedspine-api | 8000 | REST API |

### Environment Variables

Copy the example and customize:

```bash
cp deploy/configs/.env.example .env
# Edit .env with your settings
```

## Production Deployment

See [deploy/docker/docker-compose.prod.yml](docker/docker-compose.prod.yml) for production configuration.

Key differences from development:
- Resource limits enforced
- Health checks required
- Persistent volumes
- Network isolation
- No exposed debug ports

## Kubernetes

Kubernetes manifests use Kustomize for environment management:

```bash
# Development
kubectl apply -k deploy/kubernetes/overlays/dev

# Production
kubectl apply -k deploy/kubernetes/overlays/prod
```
