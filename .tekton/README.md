# Tekton Triggers Configuration Guide

This directory contains Tekton Triggers configuration files for automatically triggering CI/CD pipelines on GitHub push events.

## File Descriptions

### 1. triggerbinding.yaml
Extracts parameters from GitHub webhook payload:
- `git-url`: Git repository URL
- `git-revision`: Commit SHA
- `git-ref`: Git branch/tag reference
- `repository-name`: Repository full name
- `commit-author`: Commit author
- `commit-message`: Commit message

### 2. triggertemplate.yaml
Defines a PipelineRun template that uses parameters extracted by TriggerBinding to create PipelineRuns.

### 3. eventlistener.yaml
EventListener connects TriggerBinding and TriggerTemplate, and listens for webhook events from GitHub.

**Note**: This version includes secret validation. If you haven't created `github-webhook-secret` yet, please use `eventlistener-no-secret.yaml` instead.

### 4. route.yaml
OpenShift Route exposes the EventListener service to the public network so GitHub can send webhooks.

### 5. webhook-secret.yaml
Secret for validating GitHub webhook payload (optional but recommended).

## Deployment Steps

### Step 1: Create Secret (Optional but Recommended)

```bash
# Generate a random token
TOKEN=$(openssl rand -hex 20)
echo "Generated token: $TOKEN"

# Create Secret
kubectl create secret generic github-webhook-secret \
  --from-literal=secretToken="$TOKEN" \
  -n shopcarts

# Save this token for use in GitHub webhook configuration later
```

### Step 2: Apply Trigger Resources

```bash
# Apply all Trigger resources
kubectl apply -f .tekton/triggerbinding.yaml
kubectl apply -f .tekton/triggertemplate.yaml

# Choose which EventListener version to use:
# Option A: Use version with secret validation (if Secret is created)
kubectl apply -f .tekton/eventlistener.yaml

# Option B: Use version without secret validation (if Secret is not created yet)
# kubectl apply -f .tekton/eventlistener-no-secret.yaml

# If Secret is created, apply it
kubectl apply -f .tekton/webhook-secret.yaml
```

### Step 3: Create OpenShift Route

```bash
# Apply Route
kubectl apply -f .tekton/route.yaml

# Get Route URL
kubectl get route shopcarts-listener-route -n shopcarts -o jsonpath='{.spec.host}'
```

### Step 4: Configure GitHub Webhook

1. Go to GitHub repository: Settings > Webhooks > Add webhook
2. **Payload URL**: `https://<route-host>/` (obtained from Step 3)
3. **Content type**: `application/json`
4. **Secret**: Use the token generated in Step 1 (if Secret was created)
5. **Events**: Select "Just the push event"
6. **Active**: Check the box
7. Click "Add webhook"

## Verification

### Check EventListener Pod

```bash
# Check if EventListener Pod is running
kubectl get pods -n shopcarts -l app.kubernetes.io/component=tekton-trigger

# View EventListener logs
kubectl logs -n shopcarts -l app.kubernetes.io/component=tekton-trigger -f
```

### Check Route

```bash
# Check Route status
kubectl get route shopcarts-listener-route -n shopcarts

# Get Route URL
ROUTE_URL=$(kubectl get route shopcarts-listener-route -n shopcarts -o jsonpath='{.spec.host}')
echo "EventListener URL: https://$ROUTE_URL"
```

### Test Webhook (using curl)

```bash
# Get Route URL
ROUTE_URL=$(kubectl get route shopcarts-listener-route -n shopcarts -o jsonpath='{.spec.host}')

# Send a simulated GitHub push event
curl -X POST https://$ROUTE_URL \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: $(uuidgen)" \
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
  }'
```

Expected response: `202 Accepted`

### Check PipelineRun

```bash
# View created PipelineRuns
kubectl get pipelineruns -n shopcarts -l triggers.tekton.dev/trigger=shopcarts-github-trigger

# View details of a specific PipelineRun
kubectl describe pipelinerun <pipelinerun-name> -n shopcarts
```

## Troubleshooting

### EventListener Pod Fails to Start

```bash
# Check EventListener status
kubectl describe eventlistener shopcarts-listener -n shopcarts

# Check Service
kubectl get svc -n shopcarts | grep shopcarts-listener
```

### Webhook Request Rejected

1. Check if Secret is configured correctly
2. Verify that the Secret token in GitHub webhook matches the one in Kubernetes Secret
3. Check EventListener logs for error messages

### PipelineRun Not Created

1. Check if TriggerBinding and TriggerTemplate are applied correctly
2. View EventListener logs
3. Verify that Pipeline `shopcarts-ci` exists in `shopcarts` namespace

## Notes

- Ensure `pipeline` ServiceAccount exists and has appropriate permissions
- Ensure `pipeline-pvc` PersistentVolumeClaim exists
- If using Secret validation, ensure the Secret in GitHub webhook matches the Kubernetes Secret
- EventListener automatically creates a Service with the naming format `el-<eventlistener-name>`
