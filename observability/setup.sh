#!/bin/bash
#
# OutlabsAuth Observability Setup Script
#
# This script generates config files from templates using your .env settings.
# Run this after configuring your .env file.
#
# Usage:
#   ./setup.sh              # Generate configs
#   ./setup.sh --clean      # Remove generated configs
#   ./setup.sh --validate   # Check configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Load environment variables
load_env() {
    if [ ! -f .env ]; then
        log_warn ".env file not found, creating from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            log_info "Created .env from .env.example"
            log_warn "Please review and customize .env, then run setup.sh again"
            exit 0
        else
            log_error ".env.example not found!"
            exit 1
        fi
    fi

    # Export all variables from .env
    set -a
    source .env
    set +a

    # Set defaults for any missing variables
    : ${PROJECT_NAME:=outlabs}
    : ${ENVIRONMENT:=development}
    : ${API_HOST:=host.docker.internal}
    : ${API_PORT:=8000}
    : ${API_METRICS_PATH:=/metrics}
    : ${GRAFANA_PORT:=3011}
    : ${PROMETHEUS_PORT:=9090}
    : ${LOKI_PORT:=3100}
    : ${TEMPO_PORT:=3200}
    : ${TEMPO_OTLP_GRPC_PORT:=4317}
    : ${TEMPO_OTLP_HTTP_PORT:=4318}
    : ${GRAFANA_ADMIN_PASSWORD:=admin}
    : ${PROMETHEUS_RETENTION:=15d}
    : ${PROMETHEUS_SCRAPE_INTERVAL:=10s}

    export PROJECT_NAME ENVIRONMENT API_HOST API_PORT API_METRICS_PATH
    export GRAFANA_PORT PROMETHEUS_PORT LOKI_PORT TEMPO_PORT
    export TEMPO_OTLP_GRPC_PORT TEMPO_OTLP_HTTP_PORT
    export GRAFANA_ADMIN_PASSWORD PROMETHEUS_RETENTION PROMETHEUS_SCRAPE_INTERVAL
}

# Substitute environment variables in template files
render_template() {
    local template="$1"
    local output="$2"

    if [ ! -f "$template" ]; then
        log_error "Template not found: $template"
        return 1
    fi

    # Use envsubst to replace ${VAR} placeholders
    envsubst < "$template" > "$output"
    log_info "Generated: $output"
}

# Generate all config files from templates
generate_configs() {
    log_info "Generating configs for project: $PROJECT_NAME"
    log_info "API target: $API_HOST:$API_PORT$API_METRICS_PATH"

    # Prometheus
    render_template "prometheus/prometheus.yml.template" "prometheus/prometheus.yml"

    # Promtail
    render_template "promtail/promtail.yml.template" "promtail/promtail.yml"

    log_info ""
    log_info "Configuration complete!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Start the stack:  docker compose up -d"
    log_info "  2. Open Grafana:     http://localhost:$GRAFANA_PORT"
    log_info "  3. Login:            admin / $GRAFANA_ADMIN_PASSWORD"
    log_info ""
    log_info "Make sure your API is running on port $API_PORT with metrics enabled."
}

# Clean generated files
clean() {
    log_info "Cleaning generated config files..."
    rm -f prometheus/prometheus.yml
    rm -f promtail/promtail.yml
    log_info "Done."
}

# Validate configuration
validate() {
    log_info "Validating configuration..."

    local errors=0

    # Check .env exists
    if [ ! -f .env ]; then
        log_error ".env file not found"
        errors=$((errors + 1))
    fi

    # Check generated configs exist
    if [ ! -f prometheus/prometheus.yml ]; then
        log_error "prometheus/prometheus.yml not found - run ./setup.sh first"
        errors=$((errors + 1))
    fi

    if [ ! -f promtail/promtail.yml ]; then
        log_error "promtail/promtail.yml not found - run ./setup.sh first"
        errors=$((errors + 1))
    fi

    # Check if API is reachable (optional)
    if command -v curl &> /dev/null; then
        local api_url="http://localhost:$API_PORT$API_METRICS_PATH"
        if curl -s --connect-timeout 2 "$api_url" > /dev/null 2>&1; then
            log_info "API metrics endpoint reachable: $api_url"
        else
            log_warn "API not reachable at $api_url (is your API running?)"
        fi
    fi

    if [ $errors -eq 0 ]; then
        log_info "Validation passed!"
        return 0
    else
        log_error "Validation failed with $errors error(s)"
        return 1
    fi
}

# Main
case "${1:-}" in
    --clean)
        clean
        ;;
    --validate)
        load_env
        validate
        ;;
    --help|-h)
        echo "OutlabsAuth Observability Setup"
        echo ""
        echo "Usage: ./setup.sh [option]"
        echo ""
        echo "Options:"
        echo "  (none)      Generate config files from templates"
        echo "  --clean     Remove generated config files"
        echo "  --validate  Check configuration"
        echo "  --help      Show this help message"
        ;;
    *)
        load_env
        generate_configs
        ;;
esac
