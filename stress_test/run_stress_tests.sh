#!/bin/bash

# 🔥 HARDCORE STRESS TEST ORCHESTRATOR 🔥
# This script will run different levels of stress tests against your system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${RED}"
echo "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥"
echo "🔥                                                              🔥"
echo "🔥           HARDCORE DDoS-LEVEL STRESS TEST SUITE             🔥"
echo "🔥                                                              🔥"
echo "🔥              PREPARE FOR SYSTEM ANNIHILATION!               🔥"
echo "🔥                                                              🔥"
echo "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥"
echo -e "${NC}"

# Configuration
API_HOST="http://localhost:8030"
RESULTS_DIR="stress_test_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create results directory
mkdir -p "$RESULTS_DIR"

# Function to check if API is running
check_api() {
    echo -e "${BLUE}🔍 Checking if API is running...${NC}"
    if curl -s "$API_HOST/docs" > /dev/null; then
        echo -e "${GREEN}✅ API is running at $API_HOST${NC}"
        return 0
    else
        echo -e "${RED}❌ API is not running at $API_HOST${NC}"
        echo -e "${YELLOW}💡 Start your API with: uvicorn api.main:app --reload${NC}"
        return 1
    fi
}

# Function to install dependencies
install_deps() {
    echo -e "${BLUE}📦 Installing stress test dependencies...${NC}"
    pip install -r stress_test/requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
}

# Function to run warmup test
warmup_test() {
    echo -e "${YELLOW}🔥 Running warmup test (50 users, 30 seconds)...${NC}"
    
    locust -f stress_test/locust_ddos.py \
           --host="$API_HOST" \
           --users=50 \
           --spawn-rate=5 \
           --run-time=30s \
           --headless \
           --html="$RESULTS_DIR/warmup_test_$TIMESTAMP.html" \
           --csv="$RESULTS_DIR/warmup_test_$TIMESTAMP"
    
    echo -e "${GREEN}✅ Warmup test completed${NC}"
}

# Function to run medium stress test
medium_stress_test() {
    echo -e "${YELLOW}🔥🔥 Running medium stress test (200 users, 2 minutes)...${NC}"
    
    locust -f stress_test/locust_ddos.py \
           --host="$API_HOST" \
           --users=200 \
           --spawn-rate=10 \
           --run-time=120s \
           --headless \
           --html="$RESULTS_DIR/medium_stress_$TIMESTAMP.html" \
           --csv="$RESULTS_DIR/medium_stress_$TIMESTAMP"
    
    echo -e "${GREEN}✅ Medium stress test completed${NC}"
}

# Function to run hardcore stress test
hardcore_stress_test() {
    echo -e "${RED}🔥🔥🔥 RUNNING HARDCORE STRESS TEST (500 users, 5 minutes)...${NC}"
    echo -e "${RED}⚠️  THIS WILL ABSOLUTELY PUNISH YOUR SYSTEM! ⚠️${NC}"
    
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Hardcore test cancelled${NC}"
        return 0
    fi
    
    locust -f stress_test/locust_ddos.py \
           --host="$API_HOST" \
           --users=500 \
           --spawn-rate=25 \
           --run-time=300s \
           --headless \
           --html="$RESULTS_DIR/hardcore_stress_$TIMESTAMP.html" \
           --csv="$RESULTS_DIR/hardcore_stress_$TIMESTAMP"
    
    echo -e "${GREEN}✅ Hardcore stress test completed${NC}"
}

# Function to run extreme DDoS test
extreme_ddos_test() {
    echo -e "${PURPLE}🔥🔥🔥🔥 RUNNING EXTREME DDoS TEST (1000 users, 10 minutes)...${NC}"
    echo -e "${RED}💀💀💀 THIS IS PURE SYSTEM DESTRUCTION! 💀💀💀${NC}"
    echo -e "${RED}⚠️  YOUR SYSTEM MIGHT NOT SURVIVE THIS! ⚠️${NC}"
    
    read -p "Are you ABSOLUTELY sure? This might crash your system! (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Extreme DDoS test cancelled${NC}"
        return 0
    fi
    
    echo -e "${RED}💥 LAUNCHING EXTREME ASSAULT IN 5 SECONDS...${NC}"
    sleep 5
    
    locust -f stress_test/locust_ddos.py \
           --host="$API_HOST" \
           --users=1000 \
           --spawn-rate=50 \
           --run-time=600s \
           --headless \
           --html="$RESULTS_DIR/extreme_ddos_$TIMESTAMP.html" \
           --csv="$RESULTS_DIR/extreme_ddos_$TIMESTAMP"
    
    echo -e "${GREEN}✅ Extreme DDoS test completed (if your system survived!)${NC}"
}

# Function to run async stress test
async_stress_test() {
    echo -e "${CYAN}🚀 Running async stress test...${NC}"
    
    cd stress_test
    python ddos_stress_test.py > "../$RESULTS_DIR/async_stress_$TIMESTAMP.log" 2>&1
    cd ..
    
    echo -e "${GREEN}✅ Async stress test completed${NC}"
}

# Function to generate summary report
generate_report() {
    echo -e "${BLUE}📊 Generating stress test summary...${NC}"
    
    cat > "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md" << EOF
# Stress Test Summary - $TIMESTAMP

## Test Configuration
- **API Host**: $API_HOST
- **Test Date**: $(date)
- **Results Directory**: $RESULTS_DIR

## Tests Executed
EOF

    if [ -f "$RESULTS_DIR/warmup_test_${TIMESTAMP}_stats.csv" ]; then
        echo "- ✅ Warmup Test (50 users, 30s)" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    fi

    if [ -f "$RESULTS_DIR/medium_stress_${TIMESTAMP}_stats.csv" ]; then
        echo "- ✅ Medium Stress Test (200 users, 2m)" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    fi

    if [ -f "$RESULTS_DIR/hardcore_stress_${TIMESTAMP}_stats.csv" ]; then
        echo "- ✅ Hardcore Stress Test (500 users, 5m)" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    fi

    if [ -f "$RESULTS_DIR/extreme_ddos_${TIMESTAMP}_stats.csv" ]; then
        echo "- ✅ Extreme DDoS Test (1000 users, 10m)" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    fi

    echo "" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    echo "## Files Generated" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    echo "\`\`\`" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    ls -la "$RESULTS_DIR"/*"$TIMESTAMP"* >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"
    echo "\`\`\`" >> "$RESULTS_DIR/stress_test_summary_$TIMESTAMP.md"

    echo -e "${GREEN}📋 Summary report generated: $RESULTS_DIR/stress_test_summary_$TIMESTAMP.md${NC}"
}

# Main menu
show_menu() {
    echo -e "${CYAN}"
    echo "🎯 Select your stress test level:"
    echo "1) 🔥 Warmup Test (50 users, 30s) - Light stress"
    echo "2) 🔥🔥 Medium Stress (200 users, 2m) - Moderate load"
    echo "3) 🔥🔥🔥 Hardcore Stress (500 users, 5m) - Heavy punishment"
    echo "4) 💀 Extreme DDoS (1000 users, 10m) - SYSTEM DESTRUCTION"
    echo "5) 🚀 Async Stress Test - Custom async implementation"
    echo "6) 🎪 Full Test Suite - Run all tests sequentially"
    echo "7) 📊 Generate Report Only"
    echo "8) 📊 Start Container Monitor"
    echo "9) 🛠️ Install Dependencies"
    echo "10) 🚪 Exit"
    echo -e "${NC}"
}

# Main execution
main() {
    # Check if API is running
    if ! check_api; then
        exit 1
    fi

    while true; do
        show_menu
        read -p "Enter your choice (1-10): " choice
        
        case $choice in
            1)
                warmup_test
                ;;
            2)
                medium_stress_test
                ;;
            3)
                hardcore_stress_test
                ;;
            4)
                extreme_ddos_test
                ;;
            5)
                async_stress_test
                ;;
            6)
                echo -e "${RED}🎪 RUNNING FULL TEST SUITE - PREPARE FOR TOTAL SYSTEM ASSAULT!${NC}"
                warmup_test
                sleep 10
                medium_stress_test
                sleep 30
                hardcore_stress_test
                sleep 60
                extreme_ddos_test
                async_stress_test
                generate_report
                ;;
            7)
                generate_report
                ;;
            8)
                echo -e "${CYAN}📊 Starting Container Monitor...${NC}"
                echo -e "${YELLOW}This will open a real-time dashboard of container resources${NC}"
                echo -e "${YELLOW}Run this in a separate terminal while stress testing${NC}"
                python stress_test/monitor_container.py
                ;;
            9)
                install_deps
                ;;
            10)
                echo -e "${GREEN}👋 Exiting stress test suite${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Invalid choice. Please select 1-10.${NC}"
                ;;
        esac
        
        echo -e "\n${YELLOW}Press any key to continue...${NC}"
        read -n 1 -s
        clear
    done
}

# Run main function
main "$@" 