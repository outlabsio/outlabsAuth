#!/bin/bash

# 🔥 CONTAINER SETUP FOR STRESS TESTING 🔥
# This script will restart containers with resource constraints

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${RED}"
echo "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥"
echo "🔥                                                            🔥"
echo "🔥       SETTING UP CONTAINERS FOR STRESS TESTING           🔥"
echo "🔥                                                            🔥"
echo "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥"
echo -e "${NC}"

echo -e "${BLUE}📋 Container Resource Configuration:${NC}"
echo -e "${CYAN}   API Server:${NC}"
echo -e "   - Memory: 8GB (limit), 2GB (reserved)"
echo -e "   - CPU: 4 cores"
echo -e "   - Workers: 4"
echo -e "   - Port: 8030"
echo -e "${CYAN}   MongoDB:${NC}"
echo -e "   - Memory: 4GB (limit), 1GB (reserved)"
echo -e "   - CPU: 2 cores"
echo -e "   - Port: 27017"
echo ""

echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker compose down

echo -e "${YELLOW}🧹 Cleaning up...${NC}"
docker system prune -f

echo -e "${YELLOW}🚀 Starting containers with resource constraints...${NC}"
docker compose up -d --build

echo -e "${BLUE}⏳ Waiting for containers to be ready...${NC}"
sleep 10

echo -e "${BLUE}🔍 Checking container status...${NC}"
docker compose ps

echo -e "${BLUE}📊 Container resource limits:${NC}"
echo -e "${CYAN}API Container:${NC}"
docker stats outlabs_auth_api --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

echo -e "${CYAN}MongoDB Container:${NC}"
docker stats outlabs_auth_mongo --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

echo -e "${GREEN}✅ Containers are ready for stress testing!${NC}"
echo -e "${YELLOW}🎯 API available at: http://localhost:8030${NC}"
echo -e "${YELLOW}📚 API docs at: http://localhost:8030/docs${NC}"
echo -e "${YELLOW}🗄️ MongoDB at: localhost:27017${NC}"

echo -e "${BLUE}🔥 Ready to launch stress tests!${NC}"
echo -e "${CYAN}Run: ./stress_test/run_stress_tests.sh${NC}" 