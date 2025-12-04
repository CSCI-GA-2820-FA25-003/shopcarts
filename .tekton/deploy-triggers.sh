#!/bin/bash
# Tekton Triggers 快速部署腳本

set -e

NAMESPACE="shopcarts"
USE_SECRET=false

# 解析參數
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-secret)
            USE_SECRET=true
            shift
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        *)
            echo "未知參數: $1"
            echo "用法: $0 [--with-secret] [--namespace NAMESPACE]"
            exit 1
            ;;
    esac
done

echo "========================================="
echo "部署 Tekton Triggers"
echo "命名空間: $NAMESPACE"
echo "使用 Secret 驗證: $USE_SECRET"
echo "========================================="
echo ""

# 檢查命名空間
if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo "錯誤: 命名空間 '$NAMESPACE' 不存在"
    exit 1
fi

# 部署 TriggerBinding
echo "1. 部署 TriggerBinding..."
kubectl apply -f .tekton/triggerbinding.yaml
echo "   ✓ TriggerBinding 已部署"

# 部署 TriggerTemplate
echo ""
echo "2. 部署 TriggerTemplate..."
kubectl apply -f .tekton/triggertemplate.yaml
echo "   ✓ TriggerTemplate 已部署"

# 部署 EventListener
echo ""
echo "3. 部署 EventListener..."
if [ "$USE_SECRET" = true ]; then
    # 檢查 Secret 是否存在
    if ! kubectl get secret github-webhook-secret -n "$NAMESPACE" &>/dev/null; then
        echo "   警告: Secret 'github-webhook-secret' 不存在"
        echo "   請先創建 Secret 或使用 --without-secret 選項"
        read -p "   是否繼續部署？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    kubectl apply -f .tekton/eventlistener.yaml
    echo "   ✓ EventListener (帶 secret 驗證) 已部署"
else
    kubectl apply -f .tekton/eventlistener-no-secret.yaml
    echo "   ✓ EventListener (不帶 secret 驗證) 已部署"
fi

# 部署 Route
echo ""
echo "4. 部署 OpenShift Route..."
kubectl apply -f .tekton/route.yaml
echo "   ✓ Route 已部署"

# 等待 EventListener Pod 就緒
echo ""
echo "5. 等待 EventListener Pod 就緒..."
sleep 3
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=tekton-trigger -n "$NAMESPACE" --timeout=60s || {
    echo "   警告: EventListener Pod 未在 60 秒內就緒"
    echo "   請檢查 Pod 狀態: kubectl get pods -n $NAMESPACE -l app.kubernetes.io/component=tekton-trigger"
}

# 獲取 Route URL
echo ""
echo "6. 獲取 Route URL..."
ROUTE_URL=$(kubectl get route shopcarts-listener-route -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_URL" ]; then
    echo "   ✓ Route URL: https://$ROUTE_URL"
    echo ""
    echo "   請在 GitHub repository settings > Webhooks 中設置此 URL"
else
    echo "   ⚠ 無法獲取 Route URL"
fi

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="
echo ""
echo "下一步："
echo "1. 在 GitHub repository 設置 webhook:"
echo "   URL: https://$ROUTE_URL"
echo "   Content type: application/json"
if [ "$USE_SECRET" = true ]; then
    echo "   Secret: (使用 github-webhook-secret 中的 token)"
fi
echo "   Events: Just the push event"
echo ""
echo "2. 驗證設置:"
echo "   ./.tekton/verify-triggers.sh"
echo ""

