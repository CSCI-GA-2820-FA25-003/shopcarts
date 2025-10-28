# Kubernetes Deployment for Shopcarts Service

This directory contains Kubernetes manifests for deploying the Shopcarts microservice with PostgreSQL database to a K3D local cluster.

## Prerequisites

- Docker
- K3D installed (`brew install k3d` on macOS)
- kubectl installed
- Make

## Quick Start

1. **Create the K3D cluster:**
   ```bash
   make cluster
   ```

2. **Build and deploy the service:**
   ```bash
   make deploy
   ```
   This will:
   - Build the Docker image
   - Import it to the K3D cluster
   - Create the namespace
   - Deploy PostgreSQL
   - Deploy the Shopcarts service

3. **Check the deployment status:**
   ```bash
   kubectl get nodes
   kubectl get pods -n shopcarts
   kubectl get services -n shopcarts
   ```

4. **Access the service:**
   ```bash
   curl http://localhost:8080/
   ```

5. **Clean up:**
   ```bash
   make cluster-rm
   ```

## Available Make Targets

- `make cluster` - Create a K3D cluster with registry and load balancer
- `make cluster-rm` - Remove the K3D cluster
- `make cluster-check` - Check if cluster exists
- `make deploy` - Build, push, and deploy the service
- `make build` - Build the Docker image
- `make push` - Import image to K3D cluster

## Architecture

The deployment includes:

- **Namespace**: `shopcarts` - Isolates the deployment
- **PostgreSQL**: Database server with ConfigMap and Secret for configuration
- **Shopcarts**: Flask application with ConfigMap for environment variables
- **Services**: ClusterIP services for internal communication
- **Ingress**: Routes external traffic to the shopcarts service

## Verification

After deploying, verify the deployment:

```bash
# Check all resources
kubectl get all -n shopcarts

# Check pod logs
kubectl logs -n shopcarts deployment/shopcarts -f

# Test the API
curl http://localhost:8080/shopcarts -H "Content-Type: application/json" \
  -d '{"customer_id": 1}'
```

## Troubleshooting

- If pods are not starting, check logs: `kubectl logs -n shopcarts <pod-name>`
- If image pull errors occur, ensure the image was pushed: `k3d images list`
- Check cluster status: `kubectl get nodes`
- Check postgres connection: `kubectl exec -n shopcarts deployment/postgres -it -- psql -U postgres`

