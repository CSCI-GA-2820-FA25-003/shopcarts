#!/bin/bash
# Tekton Triggers 驗證腳本

set -e

NAMESPACE="shopcarts"
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_NC='\033[0m' # No Color

echo "========================================="
echo "Tekton Triggers 驗證腳本"
echo "========================================="
echo ""

# 檢查命名空間
echo "1. 檢查命名空間..."
if kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} 命名空間 '$NAMESPACE' 存在"
else
    echo -e "${COLOR_RED}✗${COLOR_NC} 命名空間 '$NAMESPACE' 不存在"
    exit 1
fi

# 檢查 TriggerBinding
echo ""
echo "2. 檢查 TriggerBinding..."
if kubectl get triggerbinding shopcarts-github-binding -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} TriggerBinding 'shopcarts-github-binding' 存在"
else
    echo -e "${COLOR_RED}✗${COLOR_NC} TriggerBinding 'shopcarts-github-binding' 不存在"
fi

# 檢查 TriggerTemplate
echo ""
echo "3. 檢查 TriggerTemplate..."
if kubectl get triggertemplate shopcarts-pipeline-template -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} TriggerTemplate 'shopcarts-pipeline-template' 存在"
else
    echo -e "${COLOR_RED}✗${COLOR_NC} TriggerTemplate 'shopcarts-pipeline-template' 不存在"
fi

# 檢查 EventListener
echo ""
echo "4. 檢查 EventListener..."
if kubectl get eventlistener shopcarts-listener -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} EventListener 'shopcarts-listener' 存在"
    
    # 檢查 EventListener 狀態
    READY=$(kubectl get eventlistener shopcarts-listener -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
    if [ "$READY" == "True" ]; then
        echo -e "${COLOR_GREEN}✓${COLOR_NC} EventListener 狀態: Ready"
    else
        echo -e "${COLOR_YELLOW}⚠${COLOR_NC} EventListener 狀態: $READY"
    fi
else
    echo -e "${COLOR_RED}✗${COLOR_NC} EventListener 'shopcarts-listener' 不存在"
fi

# 檢查 EventListener Pod
echo ""
echo "5. 檢查 EventListener Pod..."
PODS=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=tekton-trigger --no-headers 2>/dev/null | wc -l)
if [ "$PODS" -gt 0 ]; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} 找到 $PODS 個 EventListener Pod(s)"
    kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=tekton-trigger
else
    echo -e "${COLOR_RED}✗${COLOR_NC} 未找到 EventListener Pod"
fi

# 檢查 EventListener Service
echo ""
echo "6. 檢查 EventListener Service..."
if kubectl get svc el-shopcarts-listener -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} EventListener Service 'el-shopcarts-listener' 存在"
else
    echo -e "${COLOR_YELLOW}⚠${COLOR_NC} EventListener Service 'el-shopcarts-listener' 不存在（EventListener 創建後會自動生成）"
fi

# 檢查 Route
echo ""
echo "7. 檢查 OpenShift Route..."
if kubectl get route shopcarts-listener-route -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} Route 'shopcarts-listener-route' 存在"
    ROUTE_URL=$(kubectl get route shopcarts-listener-route -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    if [ -n "$ROUTE_URL" ]; then
        echo -e "${COLOR_GREEN}  Route URL: https://$ROUTE_URL${COLOR_NC}"
    fi
else
    echo -e "${COLOR_YELLOW}⚠${COLOR_NC} Route 'shopcarts-listener-route' 不存在"
fi

# 檢查 Secret（可選）
echo ""
echo "8. 檢查 Webhook Secret（可選）..."
if kubectl get secret github-webhook-secret -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} Secret 'github-webhook-secret' 存在"
else
    echo -e "${COLOR_YELLOW}⚠${COLOR_NC} Secret 'github-webhook-secret' 不存在（可選，但建議使用）"
fi

# 檢查 Pipeline
echo ""
echo "9. 檢查 Pipeline..."
if kubectl get pipeline shopcarts-ci -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} Pipeline 'shopcarts-ci' 存在"
else
    echo -e "${COLOR_RED}✗${COLOR_NC} Pipeline 'shopcarts-ci' 不存在"
fi

# 檢查 ServiceAccount
echo ""
echo "10. 檢查 ServiceAccount..."
if kubectl get serviceaccount pipeline -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} ServiceAccount 'pipeline' 存在"
else
    echo -e "${COLOR_RED}✗${COLOR_NC} ServiceAccount 'pipeline' 不存在"
fi

# 檢查 PVC
echo ""
echo "11. 檢查 PersistentVolumeClaim..."
if kubectl get pvc pipeline-pvc -n "$NAMESPACE" &>/dev/null; then
    echo -e "${COLOR_GREEN}✓${COLOR_NC} PVC 'pipeline-pvc' 存在"
else
    echo -e "${COLOR_RED}✗${COLOR_NC} PVC 'pipeline-pvc' 不存在"
fi

# 測試 Webhook（如果 Route 存在）
echo ""
if kubectl get route shopcarts-listener-route -n "$NAMESPACE" &>/dev/null; then
    ROUTE_URL=$(kubectl get route shopcarts-listener-route -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    if [ -n "$ROUTE_URL" ]; then
        echo "12. 測試 Webhook 連接..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://$ROUTE_URL" \
            -H "Content-Type: application/json" \
            -H "X-GitHub-Event: push" \
            -H "X-GitHub-Delivery: $(uuidgen 2>/dev/null || echo 'test-delivery-id')" \
            -d '{
                "ref": "refs/heads/master",
                "after": "abc123def456",
                "repository": {
                    "clone_url": "https://github.com/CSCI-GA-2820-FA25-003/shopcarts",
                    "full_name": "CSCI-GA-2820-FA25-003/shopcarts"
                },
                "head_commit": {
                    "author": {
                        "name": "Test User"
                    },
                    "message": "Test commit"
                }
            }' 2>/dev/null || echo "000")
        
        if [ "$HTTP_CODE" == "202" ]; then
            echo -e "${COLOR_GREEN}✓${COLOR_NC} Webhook 測試成功 (HTTP $HTTP_CODE)"
        elif [ "$HTTP_CODE" == "000" ]; then
            echo -e "${COLOR_YELLOW}⚠${COLOR_NC} 無法連接到 Route（可能是網路問題或 TLS 配置）"
        else
            echo -e "${COLOR_YELLOW}⚠${COLOR_NC} Webhook 測試返回 HTTP $HTTP_CODE（預期 202）"
        fi
    fi
fi

echo ""
echo "========================================="
echo "驗證完成"
echo "========================================="

