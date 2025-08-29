#!/bin/bash

# AI Venture Architect Deployment Script
# Usage: ./deploy.sh [environment] [version]

set -euo pipefail

# Configuration
ENVIRONMENT=${1:-staging}
VERSION=${2:-latest}
NAMESPACE="ai-venture-architect"
REGISTRY="your-registry.com"
PROJECT_NAME="ai-venture-architect"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    for tool in docker kubectl helm; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check Kubernetes connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Build and push Docker images
build_and_push_images() {
    log_info "Building and pushing Docker images..."
    
    # Build API image
    log_info "Building API image..."
    docker build -t ${REGISTRY}/${PROJECT_NAME}/api:${VERSION} ./apps/api
    docker push ${REGISTRY}/${PROJECT_NAME}/api:${VERSION}
    
    # Build Web image
    log_info "Building Web image..."
    docker build -t ${REGISTRY}/${PROJECT_NAME}/web:${VERSION} ./apps/web
    docker push ${REGISTRY}/${PROJECT_NAME}/web:${VERSION}
    
    # Build Workers image
    log_info "Building Workers image..."
    docker build -t ${REGISTRY}/${PROJECT_NAME}/workers:${VERSION} ./apps/workers
    docker push ${REGISTRY}/${PROJECT_NAME}/workers:${VERSION}
    
    log_success "Images built and pushed successfully"
}

# Deploy infrastructure components
deploy_infrastructure() {
    log_info "Deploying infrastructure components..."
    
    # Create namespace if it doesn't exist
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/namespace.yaml
    
    # Deploy secrets and config maps
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/secrets.yaml
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/configmaps.yaml
    
    # Deploy PostgreSQL
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    helm upgrade --install postgres bitnami/postgresql \
        --namespace ${NAMESPACE} \
        --set auth.postgresPassword=${POSTGRES_PASSWORD} \
        --set auth.database=ai_venture_architect \
        --set primary.persistence.size=100Gi \
        --set primary.resources.requests.memory=2Gi \
        --set primary.resources.requests.cpu=1000m \
        --set primary.resources.limits.memory=4Gi \
        --set primary.resources.limits.cpu=2000m
    
    # Deploy Redis
    helm upgrade --install redis bitnami/redis \
        --namespace ${NAMESPACE} \
        --set auth.password=${REDIS_PASSWORD} \
        --set master.persistence.size=20Gi \
        --set master.resources.requests.memory=512Mi \
        --set master.resources.requests.cpu=250m
    
    # Deploy OpenSearch
    helm repo add opensearch https://opensearch-project.github.io/helm-charts/
    helm upgrade --install opensearch opensearch/opensearch \
        --namespace ${NAMESPACE} \
        --set replicas=1 \
        --set minimumMasterNodes=1 \
        --set persistence.size=100Gi \
        --set resources.requests.memory=2Gi \
        --set resources.requests.cpu=1000m
    
    log_success "Infrastructure components deployed"
}

# Deploy application components
deploy_application() {
    log_info "Deploying application components..."
    
    # Update image tags in deployment files
    sed -i "s|image: .*api:.*|image: ${REGISTRY}/${PROJECT_NAME}/api:${VERSION}|g" \
        deploy/kubernetes/${ENVIRONMENT}/api-deployment.yaml
    sed -i "s|image: .*web:.*|image: ${REGISTRY}/${PROJECT_NAME}/web:${VERSION}|g" \
        deploy/kubernetes/${ENVIRONMENT}/web-deployment.yaml
    sed -i "s|image: .*workers:.*|image: ${REGISTRY}/${PROJECT_NAME}/workers:${VERSION}|g" \
        deploy/kubernetes/${ENVIRONMENT}/workers-deployment.yaml
    
    # Deploy API
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/api-deployment.yaml
    
    # Deploy Web
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/web-deployment.yaml
    
    # Deploy Workers
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/workers-deployment.yaml
    
    # Deploy Ingress
    kubectl apply -f deploy/kubernetes/${ENVIRONMENT}/ingress.yaml
    
    log_success "Application components deployed"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Wait for API pods to be ready
    kubectl wait --for=condition=ready pod -l app=api -n ${NAMESPACE} --timeout=300s
    
    # Run migrations
    kubectl exec -n ${NAMESPACE} deployment/api-deployment -- \
        python -m alembic upgrade head
    
    log_success "Database migrations completed"
}

# Deploy monitoring stack
deploy_monitoring() {
    log_info "Deploying monitoring stack..."
    
    # Add Prometheus Helm repo
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    # Deploy Prometheus
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --set prometheus.prometheusSpec.retention=30d \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi \
        --set grafana.adminPassword=${GRAFANA_PASSWORD}
    
    # Deploy custom dashboards
    kubectl apply -f deploy/kubernetes/monitoring/
    
    log_success "Monitoring stack deployed"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check pod status
    log_info "Checking pod status..."
    kubectl get pods -n ${NAMESPACE}
    
    # Check services
    log_info "Checking services..."
    kubectl get services -n ${NAMESPACE}
    
    # Wait for all deployments to be ready
    log_info "Waiting for deployments to be ready..."
    kubectl wait --for=condition=available deployment --all -n ${NAMESPACE} --timeout=600s
    
    # Run health checks
    log_info "Running health checks..."
    
    # Get API service URL
    API_URL=$(kubectl get service api-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -z "$API_URL" ]; then
        API_URL=$(kubectl get service api-service -n ${NAMESPACE} -o jsonpath='{.spec.clusterIP}')
    fi
    
    # Health check with retry
    for i in {1..10}; do
        if curl -f "http://${API_URL}/v1/health" &> /dev/null; then
            log_success "Health check passed"
            break
        else
            log_warning "Health check failed, retrying in 30 seconds... (${i}/10)"
            sleep 30
        fi
        
        if [ $i -eq 10 ]; then
            log_error "Health check failed after 10 attempts"
            exit 1
        fi
    done
    
    log_success "Deployment verification completed"
}

# Rollback function
rollback() {
    log_warning "Rolling back deployment..."
    
    # Rollback deployments
    kubectl rollout undo deployment/api-deployment -n ${NAMESPACE}
    kubectl rollout undo deployment/web-deployment -n ${NAMESPACE}
    kubectl rollout undo deployment/workers-deployment -n ${NAMESPACE}
    
    # Wait for rollback to complete
    kubectl rollout status deployment/api-deployment -n ${NAMESPACE}
    kubectl rollout status deployment/web-deployment -n ${NAMESPACE}
    kubectl rollout status deployment/workers-deployment -n ${NAMESPACE}
    
    log_success "Rollback completed"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    # Add cleanup logic here
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting deployment of AI Venture Architect ${VERSION} to ${ENVIRONMENT}"
    
    # Trap for cleanup on exit
    trap cleanup EXIT
    
    # Load environment variables
    if [ -f "deploy/environments/${ENVIRONMENT}.env" ]; then
        source "deploy/environments/${ENVIRONMENT}.env"
    else
        log_error "Environment file deploy/environments/${ENVIRONMENT}.env not found"
        exit 1
    fi
    
    # Run deployment steps
    check_prerequisites
    build_and_push_images
    deploy_infrastructure
    deploy_application
    run_migrations
    
    if [ "${ENVIRONMENT}" = "production" ]; then
        deploy_monitoring
    fi
    
    verify_deployment
    
    log_success "Deployment completed successfully!"
    log_info "Application URL: https://ai-venture-architect.${ENVIRONMENT}.com"
    log_info "Monitoring URL: https://monitoring.ai-venture-architect.${ENVIRONMENT}.com"
}

# Handle script arguments
case "${1:-}" in
    "rollback")
        rollback
        ;;
    "verify")
        verify_deployment
        ;;
    *)
        main
        ;;
esac
