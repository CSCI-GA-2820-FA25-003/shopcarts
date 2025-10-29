# DevContainer Environment Setup

This guide helps you set up and use the DevContainer environment for Kubernetes development.

## Prerequisites

- Docker Desktop installed and running
- VS Code with Dev Containers extension
- Git

## Getting Started

### 1. Open in DevContainer

**Option A: VS Code Command Palette**
1. Open VS Code
2. Open this project folder
3. Press `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P` (Windows/Linux)
4. Type "Dev Containers: Reopen in Container"
5. Select "Reopen in Container"

**Option B: Command Line**
```bash
code .
```
Then follow Option A steps 3-5.

### 2. Verify DevContainer Environment

Once inside the DevContainer, verify the environment:

```bash
# Check if you're in the container
whoami  # Should show "vscode"
pwd     # Should show "/app"

# Check installed tools
kubectl version --client
k3d version
docker version
```

### 3. Create Kubernetes Cluster

```bash
# Create local K3D cluster
make cluster

# Verify cluster
kubectl get nodes
```

### 4. Deploy Services

```bash
# Deploy PostgreSQL StatefulSet and Shopcarts service
make deploy

# Check deployment status
kubectl get all -n shopcarts
```

### 5. Test the Service

```bash
# Test service accessibility
curl http://localhost:8080/

# Create a shopcart
curl -X POST http://localhost:8080/shopcarts \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1}'
```

## DevContainer Features

The DevContainer includes:

- **Python 3.11** with pipenv
- **PostgreSQL 15** database
- **Docker-in-Docker** for container builds
- **Kubernetes tools**: kubectl, helm, minikube
- **K3D** for local Kubernetes clusters
- **VS Code extensions**: Python, Kubernetes, Docker, YAML
- **Pre-configured settings**: Python formatting, testing, linting

## File Structure

```
.devcontainer/
├── devcontainer.json    # DevContainer configuration
├── docker-compose.yml   # Multi-service setup
├── Dockerfile          # Custom container image
└── scripts/            # Setup scripts

k8s/
├── namespace.yaml
├── postgres/
│   ├── statefulset.yaml  # PostgreSQL StatefulSet
│   └── service.yaml      # Headless + ClusterIP services
├── shopcarts-deployment.yaml
├── shopcarts-configmap.yaml
└── ingress.yaml
```

## Troubleshooting

### Port Forwarding
If services aren't accessible:
```bash
# Check port forwarding
kubectl get svc -n shopcarts
kubectl port-forward -n shopcarts svc/shopcarts 8080:80
```

### Database Connection Issues
```bash
# Check PostgreSQL StatefulSet
kubectl get statefulset -n shopcarts
kubectl get pvc -n shopcarts
kubectl logs -n shopcarts statefulset/postgres
```

### Clean Up
```bash
# Remove cluster
make cluster-rm

# Or manually
k3d cluster delete nyu-devops
```

## Development Workflow

1. **Start DevContainer**: Reopen in container
2. **Create cluster**: `make cluster`
3. **Deploy services**: `make deploy`
4. **Develop**: Make changes to code
5. **Rebuild**: `make build && make push`
6. **Redeploy**: `kubectl rollout restart deployment/shopcarts -n shopcarts`
7. **Test**: Use curl or test scripts
8. **Clean up**: `make cluster-rm` when done

This environment provides a complete Kubernetes development setup with persistent storage and stable networking for PostgreSQL.
