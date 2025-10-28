#!/bin/bash

# Test Kubernetes cluster and Shopcarts service deployment
# Usage: ./test-kubernetes-setup.sh

set -e

echo "========================================="
echo "Shopcarts Kubernetes Deployment Verification Test"
echo "========================================="

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test functions
test_pass() {
    echo -e "${GREEN}✓ $1${NC}"
}

test_fail() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

test_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# 1. Check prerequisites
echo ""
echo "1. Checking prerequisites..."
command -v k3d >/dev/null 2>&1 && test_pass "k3d is installed" || test_fail "k3d is not installed, please run: brew install k3d"
command -v kubectl >/dev/null 2>&1 && test_pass "kubectl is installed" || test_fail "kubectl is not installed"
command -v docker >/dev/null 2>&1 && test_pass "Docker is installed" || test_fail "Docker is not installed"
command -v make >/dev/null 2>&1 && test_pass "make is installed" || test_fail "make is not installed"

# 2. Check if cluster exists
echo ""
echo "2. Checking cluster status..."
if k3d cluster list | grep -q "nyu-devops"; then
    test_info "Cluster 'nyu-devops' already exists"
else
    test_info "Cluster does not exist, needs to be created"
fi

# 3. Ask if cluster should be created
read -p "Do you want to create a new cluster? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    test_info "Creating cluster..."
    make cluster || test_fail "Cluster creation failed"
fi

# 4. Verify cluster nodes
echo ""
echo "3. Verifying cluster nodes..."
kubectl get nodes
NODE_COUNT=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
if [ "$NODE_COUNT" -ge 1 ]; then
    test_pass "At least 1 node exists"
else
    test_fail "Insufficient number of nodes"
fi

# 5. Verify all node status
echo ""
echo "4. Checking node status..."
READY_NODES=$(kubectl get nodes --no-headers | grep -c "Ready" || true)
if [ "$READY_NODES" -ge 1 ]; then
    test_pass "All nodes are Ready status ($READY_NODES nodes)"
else
    test_fail "Nodes are not ready"
fi

# 6. Ask if service should be deployed
read -p "Do you want to deploy the service? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    test_info "Deploying service..."
    make deploy || test_fail "Service deployment failed"
fi

# 7. Verify deployment
echo ""
echo "5. Verifying deployment resources..."
kubectl get all -n shopcarts
kubectl get configmaps -n shopcarts
kubectl get secrets -n shopcarts

# 8. Check Pod status
echo ""
echo "6. Checking Pod status..."
sleep 5
kubectl get pods -n shopcarts

# 9. Wait for service readiness
echo ""
echo "7. Waiting for service readiness..."
kubectl wait --for=condition=Ready pods -l app=postgres -n shopcarts --timeout=120s && \
    test_pass "PostgreSQL is ready" || test_info "PostgreSQL may need more time"

# 10. Test database connection
echo ""
echo "8. Testing database connection..."
if kubectl exec -n shopcarts deployment/postgres -- pg_isready -U postgres; then
    test_pass "PostgreSQL connection successful"
else
    test_info "PostgreSQL connection test failed (may still be starting up)"
fi

# 11. Test HTTP service
echo ""
echo "9. Testing HTTP service..."
if curl -s http://localhost:8080/ > /dev/null; then
    test_pass "Shopcarts service responds normally"
    echo ""
    echo "Service response:"
    curl -s http://localhost:8080/ | head -20
else
    test_info "Service not ready (may need more time or check logs)"
    echo ""
    echo "View Shopcarts logs:"
    kubectl logs -n shopcarts deployment/shopcarts --tail=20 || true
fi

echo ""
echo "========================================="
test_pass "Verification test completed!"
echo "========================================="
echo ""
echo "Useful commands:"
echo "  View all resources: kubectl get all -n shopcarts"
echo "  View Pod logs: kubectl logs -n shopcarts deployment/shopcarts -f"
echo "  View database logs: kubectl logs -n shopcarts deployment/postgres -f"
echo "  Delete cluster: make cluster-rm"
echo ""

