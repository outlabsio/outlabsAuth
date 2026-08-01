#!/bin/bash
#
# Test script for OutlabsAuth Observability Stack
#
# Runs automated tests to verify the observability setup works correctly.
#
# Usage:
#   ./test.sh              # Run all tests
#   ./test.sh --quick      # Quick tests (no docker)
#   ./test.sh --cleanup    # Clean up test artifacts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; PASSED=$((PASSED + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; FAILED=$((FAILED + 1)); }
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

# =============================================================================
# Test Functions
# =============================================================================

test_env_example_exists() {
    if [ -f .env.example ]; then
        log_pass ".env.example exists"
    else
        log_fail ".env.example not found"
    fi
}

test_setup_script_exists() {
    if [ -x setup.sh ]; then
        log_pass "setup.sh exists and is executable"
    else
        log_fail "setup.sh not found or not executable"
    fi
}

test_docker_compose_exists() {
    if [ -f docker-compose.yml ]; then
        log_pass "docker-compose.yml exists"
    else
        log_fail "docker-compose.yml not found"
    fi
}

test_templates_exist() {
    local templates=(
        "prometheus/prometheus.yml.template"
        "promtail/promtail.yml.template"
    )

    for template in "${templates[@]}"; do
        if [ -f "$template" ]; then
            log_pass "Template exists: $template"
        else
            log_fail "Template not found: $template"
        fi
    done
}

test_grafana_configs_exist() {
    local configs=(
        "grafana/provisioning/datasources/datasources.yml"
        "grafana/provisioning/dashboards/dashboards.yml"
        "grafana/dashboards/outlabs-auth.json"
    )

    for config in "${configs[@]}"; do
        if [ -f "$config" ]; then
            log_pass "Grafana config exists: $config"
        else
            log_fail "Grafana config not found: $config"
        fi
    done
}

test_tempo_config_exists() {
    if [ -f tempo/tempo.yml ]; then
        log_pass "tempo/tempo.yml exists"
    else
        log_fail "tempo/tempo.yml not found"
    fi
}

test_setup_creates_env() {
    # Clean up first
    rm -f .env prometheus/prometheus.yml promtail/promtail.yml

    # Run setup (should create .env from example)
    ./setup.sh > /dev/null 2>&1

    if [ -f .env ]; then
        log_pass "setup.sh creates .env from .env.example"
    else
        log_fail "setup.sh did not create .env"
    fi

    # Run setup again to generate configs (first run exits after creating .env)
    ./setup.sh > /dev/null 2>&1
}

test_setup_generates_prometheus_config() {
    if [ -f prometheus/prometheus.yml ]; then
        log_pass "setup.sh generates prometheus/prometheus.yml"

        # Check that variables were substituted
        if grep -q '\${' prometheus/prometheus.yml; then
            log_fail "prometheus.yml contains unsubstituted variables"
        else
            log_pass "prometheus.yml variables substituted correctly"
        fi
    else
        log_fail "prometheus/prometheus.yml not generated"
    fi
}

test_setup_generates_promtail_config() {
    if [ -f promtail/promtail.yml ]; then
        log_pass "setup.sh generates promtail/promtail.yml"

        # Check that variables were substituted
        if grep -q '\${' promtail/promtail.yml; then
            log_fail "promtail.yml contains unsubstituted variables"
        else
            log_pass "promtail.yml variables substituted correctly"
        fi
    else
        log_fail "promtail/promtail.yml not generated"
    fi
}

test_custom_project_name() {
    # Clean and regenerate with custom name
    rm -f .env prometheus/prometheus.yml promtail/promtail.yml

    # Create .env with custom project name
    cp .env.example .env
    sed -i.bak 's/PROJECT_NAME=outlabs/PROJECT_NAME=testproject/' .env
    rm -f .env.bak

    ./setup.sh > /dev/null 2>&1

    if grep -q "testproject" prometheus/prometheus.yml; then
        log_pass "Custom PROJECT_NAME applied to prometheus.yml"
    else
        log_fail "Custom PROJECT_NAME not found in prometheus.yml"
    fi

    # Clean up
    rm -f .env prometheus/prometheus.yml promtail/promtail.yml
}

test_docker_compose_syntax() {
    if command -v docker &> /dev/null; then
        # Create minimal .env for docker compose config check
        cp .env.example .env 2>/dev/null || true

        if docker compose config > /dev/null 2>&1; then
            log_pass "docker-compose.yml syntax is valid"
        else
            log_fail "docker-compose.yml has syntax errors"
        fi

        rm -f .env
    else
        log_info "Skipping docker compose syntax check (docker not available)"
    fi
}

test_grafana_dashboard_json() {
    if command -v python3 &> /dev/null; then
        if python3 -c "import json; json.load(open('grafana/dashboards/outlabs-auth.json'))" 2>/dev/null; then
            log_pass "Grafana dashboard JSON is valid"
        else
            log_fail "Grafana dashboard JSON is invalid"
        fi
    else
        log_info "Skipping JSON validation (python3 not available)"
    fi
}

# =============================================================================
# Docker Tests (require running docker)
# =============================================================================

test_docker_stack_starts() {
    log_info "Starting docker stack (this may take a minute)..."

    # Setup
    cp .env.example .env
    ./setup.sh > /dev/null 2>&1

    # Start stack
    if docker compose up -d > /dev/null 2>&1; then
        log_pass "Docker stack started"

        # Wait for services to be ready
        sleep 10

        # Check Prometheus
        if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
            log_pass "Prometheus is ready"
        else
            log_fail "Prometheus not responding"
        fi

        # Check Grafana
        if curl -s http://localhost:3011/api/health > /dev/null 2>&1; then
            log_pass "Grafana is ready"
        else
            log_fail "Grafana not responding"
        fi

        # Check Loki
        if curl -s http://localhost:3100/ready > /dev/null 2>&1; then
            log_pass "Loki is ready"
        else
            log_fail "Loki not responding"
        fi

        # Stop stack
        docker compose down > /dev/null 2>&1
        log_pass "Docker stack stopped cleanly"
    else
        log_fail "Docker stack failed to start"
    fi

    # Cleanup
    rm -f .env prometheus/prometheus.yml promtail/promtail.yml
}

# =============================================================================
# Main
# =============================================================================

cleanup() {
    log_info "Cleaning up test artifacts..."
    rm -f .env prometheus/prometheus.yml promtail/promtail.yml
    log_info "Done."
}

run_quick_tests() {
    echo ""
    echo "Running quick tests (no docker)..."
    echo "=================================="
    echo ""

    test_env_example_exists
    test_setup_script_exists
    test_docker_compose_exists
    test_templates_exist
    test_grafana_configs_exist
    test_tempo_config_exists
    test_setup_creates_env
    test_setup_generates_prometheus_config
    test_setup_generates_promtail_config
    test_custom_project_name
    test_docker_compose_syntax
    test_grafana_dashboard_json
}

run_docker_tests() {
    echo ""
    echo "Running docker tests..."
    echo "======================="
    echo ""

    test_docker_stack_starts
}

print_summary() {
    echo ""
    echo "=================================="
    echo "Test Summary"
    echo "=================================="
    echo -e "Passed: ${GREEN}$PASSED${NC}"
    echo -e "Failed: ${RED}$FAILED${NC}"
    echo ""

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed.${NC}"
        return 1
    fi
}

case "${1:-}" in
    --quick)
        run_quick_tests
        cleanup
        print_summary
        ;;
    --cleanup)
        cleanup
        ;;
    --docker)
        run_docker_tests
        cleanup
        print_summary
        ;;
    --help|-h)
        echo "OutlabsAuth Observability Test Script"
        echo ""
        echo "Usage: ./test.sh [option]"
        echo ""
        echo "Options:"
        echo "  (none)      Run all tests (quick + docker)"
        echo "  --quick     Run quick tests only (no docker)"
        echo "  --docker    Run docker tests only"
        echo "  --cleanup   Clean up test artifacts"
        echo "  --help      Show this help message"
        ;;
    *)
        run_quick_tests

        if command -v docker &> /dev/null; then
            run_docker_tests
        else
            log_info "Skipping docker tests (docker not available)"
        fi

        cleanup
        print_summary
        ;;
esac
