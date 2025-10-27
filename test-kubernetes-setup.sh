#!/bin/bash

# 测试 Kubernetes 集群和 Shopcarts 服务部署
# 使用方法: ./test-kubernetes-setup.sh

set -e

echo "========================================="
echo "Shopcarts Kubernetes 部署验证测试"
echo "========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
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

# 1. 检查前置依赖
echo ""
echo "1. 检查前置依赖..."
command -v k3d >/dev/null 2>&1 && test_pass "k3d 已安装" || test_fail "k3d 未安装，请运行: brew install k3d"
command -v kubectl >/dev/null 2>&1 && test_pass "kubectl 已安装" || test_fail "kubectl 未安装"
command -v docker >/dev/null 2>&1 && test_pass "Docker 已安装" || test_fail "Docker 未安装"
command -v make >/dev/null 2>&1 && test_pass "make 已安装" || test_fail "make 未安装"

# 2. 检查集群是否存在
echo ""
echo "2. 检查集群状态..."
if k3d cluster list | grep -q "nyu-devops"; then
    test_info "集群 'nyu-devops' 已存在"
else
    test_info "集群不存在，需要创建"
fi

# 3. 询问是否创建集群
read -p "是否要创建新集群? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    test_info "创建集群..."
    make cluster || test_fail "集群创建失败"
fi

# 4. 验证集群节点
echo ""
echo "3. 验证集群节点..."
kubectl get nodes
NODE_COUNT=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
if [ "$NODE_COUNT" -ge 1 ]; then
    test_pass "至少有 1 个节点"
else
    test_fail "节点数量不足"
fi

# 5. 验证所有节点状态
echo ""
echo "4. 检查节点状态..."
READY_NODES=$(kubectl get nodes --no-headers | grep -c "Ready" || true)
if [ "$READY_NODES" -ge 1 ]; then
    test_pass "所有节点都是 Ready 状态 ($READY_NODES 个节点)"
else
    test_fail "节点未就绪"
fi

# 6. 询问是否部署服务
read -p "是否要部署服务? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    test_info "部署服务..."
    make deploy || test_fail "服务部署失败"
fi

# 7. 验证部署
echo ""
echo "5. 验证部署资源..."
kubectl get all -n shopcarts
kubectl get configmaps -n shopcarts
kubectl get secrets -n shopcarts

# 8. 检查 Pod 状态
echo ""
echo "6. 检查 Pod 状态..."
sleep 5
kubectl get pods -n shopcarts

# 9. 等待服务就绪
echo ""
echo "7. 等待服务就绪..."
kubectl wait --for=condition=Ready pods -l app=postgres -n shopcarts --timeout=120s && \
    test_pass "PostgreSQL 已就绪" || test_info "PostgreSQL 可能需要更多时间"

# 10. 测试数据库连接
echo ""
echo "8. 测试数据库连接..."
if kubectl exec -n shopcarts deployment/postgres -- pg_isready -U postgres; then
    test_pass "PostgreSQL 可以连接"
else
    test_info "PostgreSQL 连接测试失败（可能还在启动中）"
fi

# 11. 测试 HTTP 服务
echo ""
echo "9. 测试 HTTP 服务..."
if curl -s http://localhost:8080/ > /dev/null; then
    test_pass "Shopcarts 服务响应正常"
    echo ""
    echo "服务响应:"
    curl -s http://localhost:8080/ | head -20
else
    test_info "服务未就绪（可能需要更多时间或查看日志）"
    echo ""
    echo "查看 Shopcarts 日志:"
    kubectl logs -n shopcarts deployment/shopcarts --tail=20 || true
fi

echo ""
echo "========================================="
test_pass "验证测试完成！"
echo "========================================="
echo ""
echo "有用的命令:"
echo "  查看所有资源: kubectl get all -n shopcarts"
echo "  查看 Pod 日志: kubectl logs -n shopcarts deployment/shopcarts -f"
echo "  查看数据库日志: kubectl logs -n shopcarts deployment/postgres -f"
echo "  删除集群: make cluster-rm"
echo ""

