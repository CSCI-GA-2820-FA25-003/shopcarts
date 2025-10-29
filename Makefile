# These can be overidden with env vars.
REGISTRY ?= docker.io
ORG ?= your-username
IMAGE_NAME ?= shopcarts
IMAGE_TAG ?= 1.0
IMAGE ?= $(REGISTRY)/$(ORG)/$(IMAGE_NAME):$(IMAGE_TAG)
PLATFORM ?= "linux/amd64,linux/arm64"
CLUSTER ?= nyu-devops

.SILENT:

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: all
all: help

##@ Development

.PHONY: clean
clean:	## Removes all dangling build cache
	$(info Removing all dangling build cache..)
	-docker rmi $(IMAGE)
	docker image prune -f
	docker buildx prune -f

.PHONY: install
install: ## Install Python dependencies
	$(info Installing dependencies...)
	sudo pipenv install --system --dev

.PHONY: lint
lint: ## Run the linter
	$(info Running linting...)
	-flake8 service tests --count --select=E9,F63,F7,F82 --show-source --statistics
	-flake8 service tests --count --max-complexity=10 --max-line-length=127 --statistics
	-pylint service tests --max-line-length=127

.PHONY: test
test: ## Run the unit tests
	$(info Running tests...)
	export RETRY_COUNT=1; pytest --pspec --cov=service --cov-fail-under=95 --disable-warnings

.PHONY: run
run: ## Run the service
	$(info Starting service...)
	honcho start

.PHONY: secret
secret: ## Generate a secret hex key
	$(info Generating a new secret key...)
	python3 -c 'import secrets; print(secrets.token_hex())'

##@ Kubernetes

.PHONY: cluster-check
cluster-check: ## Check if a Kubernetes cluster exists
	@k3d cluster list | grep -q $(CLUSTER) && echo "Cluster $(CLUSTER) exists" || echo "Cluster $(CLUSTER) does not exist"

.PHONY: cluster
cluster: ## Create a K3D Kubernetes cluster with load balancer and registry
	@if k3d cluster list | grep -q $(CLUSTER); then \
		echo "Cluster $(CLUSTER) already exists. Use 'make cluster-rm' to remove it first."; \
	else \
		echo "Creating Kubernetes cluster $(CLUSTER) with registry and 2 agents..."; \
		echo "Note: In Docker-in-Docker environments, k3d may report errors but the cluster should still work."; \
		k3d cluster create $(CLUSTER) --servers 1 --agents 2 --registry-create cluster-registry:0.0.0.0:5001 --port '8080:80@loadbalancer' --timeout 300s --no-rollback 2>&1 || true; \
		echo "Waiting for cluster to start..."; \
		sleep 10; \
		echo "Writing kubeconfig..."; \
		k3d kubeconfig merge $(CLUSTER) --kubeconfig-switch-context 2>&1 || k3d kubeconfig write $(CLUSTER) --kubeconfig-switch-context 2>&1 || true; \
		echo "Checking cluster status..."; \
		sleep 3; \
		kubectl get nodes 2>&1 || echo "Note: If nodes are not showing, the cluster may need more time. Try: kubectl get nodes"; \
		echo "Cluster setup complete!"; \
	fi

.PHONY: cluster-rm
cluster-rm: ## Remove a K3D Kubernetes cluster
	$(info Removing Kubernetes cluster $(CLUSTER)...)
	k3d cluster delete $(CLUSTER)

.PHONY: deploy
deploy: build cluster-import-image ## Deploy the service on local Kubernetes
	$(info Deploying service locally...)
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/postgres/service.yaml
	kubectl apply -f k8s/postgres/statefulset.yaml
	kubectl apply -f k8s/shopcarts-configmap.yaml
	kubectl apply -f k8s/shopcarts-deployment.yaml
	kubectl apply -f k8s/ingress.yaml
	@echo "Waiting for deployments to be ready..."
	@kubectl wait --for=condition=Ready pods -l app=postgres -n shopcarts --timeout=120s
	@kubectl wait --for=condition=Available deployment/shopcarts -n shopcarts --timeout=120s

.PHONY: undeploy
undeploy: ## Remove all Kubernetes resources
	$(info Removing Kubernetes resources...)
	kubectl delete -f k8s/ingress.yaml --ignore-not-found=true
	kubectl delete -f k8s/shopcarts-deployment.yaml --ignore-not-found=true
	kubectl delete -f k8s/shopcarts-configmap.yaml --ignore-not-found=true
	kubectl delete -f k8s/postgres/statefulset.yaml --ignore-not-found=true
	kubectl delete -f k8s/postgres/service.yaml --ignore-not-found=true
	kubectl delete -f k8s/namespace.yaml --ignore-not-found=true

.PHONY: url
url: ## Show the ingress URL
	$(info Getting ingress URL...)
	@kubectl get ingress -n shopcarts -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null && echo "" || kubectl get ingress -n shopcarts -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null || echo "No ingress found. Run 'make deploy' first."

############################################################
# COMMANDS FOR BUILDING THE IMAGE
############################################################

##@ Image Build and Push

.PHONY: init
init: export DOCKER_BUILDKIT=1
init:	## Creates the buildx instance
	$(info Initializing Builder...)
	-docker buildx create --use --name=qemu
	docker buildx inspect --bootstrap

.PHONY: build
build:	## Build the project container image for local platform
	$(info Building $(IMAGE)...)
	docker build --rm --pull --tag $(IMAGE) --tag $(IMAGE_NAME):$(IMAGE_TAG) .

.PHONY: push
push:	## Push the image to the container registry
	$(info Pushing $(IMAGE) to registry...)
	docker push $(IMAGE)

.PHONY: cluster-import-image
cluster-import-image: build ## Import the image to the K3D cluster
	$(info Importing $(IMAGE_NAME):$(IMAGE_TAG) to cluster $(CLUSTER)...)
	@k3d images import $(IMAGE_NAME):$(IMAGE_TAG) -c $(CLUSTER)

.PHONY: buildx
buildx:	## Build multi-platform image with buildx
	$(info Building multi-platform image $(IMAGE) for $(PLATFORM)...)
	docker buildx build --file Dockerfile --pull --platform=$(PLATFORM) --tag $(IMAGE) --push .

.PHONY: remove
remove:	## Stop and remove the buildx builder
	$(info Stopping and removing the builder image...)
	docker buildx stop
	docker buildx rm
