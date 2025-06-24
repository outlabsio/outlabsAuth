# 🔥 HARDCORE DDoS-LEVEL STRESS TEST SUITE 🔥

Welcome to the **most brutal stress testing suite** ever created for the outlabsAuth RBAC system! This suite will **absolutely punish your system** with massive concurrent load, memory pressure, and DDoS-style attacks to ensure your enterprise-grade system can handle anything.

## 🎯 **WHAT THIS WILL DO TO YOUR SYSTEM**

This stress test suite will:

- **🔥 Launch thousands of concurrent requests**
- **💥 Hammer your database with extreme load**
- **🧠 Create memory pressure with large payloads**
- **⚡ Execute burst attack patterns**
- **📊 Monitor system resources in real-time**
- **🎪 Test every endpoint under extreme conditions**

## 🚀 **QUICK START - DESTROY YOUR SYSTEM NOW!**

### 1. **Setup Containers with Resource Constraints**

```bash
# Start containers with production-like resource limits (8GB RAM, 4 CPU cores)
./stress_test/setup_containers.sh
```

This will:

- **🔥 Constrain API container**: 8GB RAM, 4 CPU cores, 4 workers
- **🗄️ Constrain MongoDB**: 4GB RAM, 2 CPU cores
- **📊 Show real-time resource usage**
- **🎯 API available at**: http://localhost:8030

### 2. **Seed Database with Realistic Test Data**

```bash
# Create foundation data (admin user, roles, permissions, basic client accounts)
python scripts/seed_test_environment.py

# Add realistic companies and users via API calls (simulates real usage)
python scripts/seed_via_api.py
```

This creates:

- **🏢 6 Client Accounts**: GreenTech Industries, MedCorp Healthcare, RetailPlus, etc.
- **👤 20+ Users**: Platform admin, client admins, managers, employees
- **👥 9 Groups**: Engineering teams, management teams, operational groups
- **🔐 Realistic Permissions**: Proper role hierarchies and access control

**Test Credentials Created:**

- Platform admin: `admin@test.com` / `admin123`
- GreenTech admin: `admin@greentech.com` / `greentech123`
- MedCorp admin: `admin@medcorp.com` / `medcorp123`
- RetailPlus admin: `admin@retailplus.com` / `retail123`

### 3. **Install Dependencies**

```bash
pip install -r stress_test/requirements.txt
```

### 4. **Launch the Orchestrator**

```bash
./stress_test/run_stress_tests.sh
```

### 5. **Choose Your Destruction Level**

- 🔥 **Warmup** (50 users) - Light stress
- 🔥🔥 **Medium** (200 users) - Moderate punishment
- 🔥🔥🔥 **Hardcore** (500 users) - Heavy destruction
- 💀 **Extreme DDoS** (1000 users) - **SYSTEM ANNIHILATION**

## 🛠️ **STRESS TEST ARSENAL**

### 🎯 **1. Locust DDoS Attack (`locust_ddos.py`)**

**Web-based distributed stress testing**

```bash
# Basic assault
locust -f stress_test/locust_ddos.py --host=http://localhost:8030

# Hardcore assault (1000 concurrent users)
locust -f stress_test/locust_ddos.py --host=http://localhost:8030 -u 1000 -r 50

# Sustained attack (5 minutes of hell)
locust -f stress_test/locust_ddos.py --host=http://localhost:8030 -u 500 -r 25 -t 300s

# Distributed attack (multiple machines)
# Master:
locust -f stress_test/locust_ddos.py --host=http://localhost:8030 --master

# Workers:
locust -f stress_test/locust_ddos.py --host=http://localhost:8030 --worker --master-host=<master-ip>
```

**Features:**

- **Multiple attack patterns** (QuickAssault, SustainedAttack, HeavyBomber)
- **Real-time web UI** at http://localhost:8089
- **Distributed testing** across multiple machines
- **Memory pressure attacks** with large payloads
- **Burst attack patterns**

### 🚀 **2. Async DDoS Attack (`ddos_stress_test.py`)**

**Pure async Python implementation for maximum performance**

```bash
cd stress_test
python ddos_stress_test.py
```

**Features:**

- **uvloop integration** for maximum async performance
- **System resource monitoring** (CPU, memory, disk, network)
- **Configurable attack patterns**
- **Real-time progress tracking**
- **Detailed performance analysis**

### 🎪 **3. Orchestrated Test Suite (`run_stress_tests.sh`)**

**Complete test orchestration with multiple scenarios**

```bash
./stress_test/run_stress_tests.sh
```

**Features:**

- **Interactive menu** for test selection
- **Automated test sequencing**
- **Results aggregation**
- **System health checking**
- **Beautiful colored output**

### 📊 **4. Container Resource Monitor (`monitor_container.py`)**

**Real-time Docker container monitoring during stress tests**

```bash
# Run in separate terminal while stress testing
python stress_test/monitor_container.py
```

**Features:**

- **Real-time resource dashboard** with live updates
- **CPU, Memory, Network, Disk I/O monitoring**
- **Color-coded status indicators** (🟢 healthy, 🟡 stressed, 🔥 choking)
- **Process count tracking**
- **Resource limit awareness**

**Monitor shows:**

- **API Container**: 8GB RAM limit, 4 CPU cores, process count
- **MongoDB Container**: 4GB RAM limit, 2 CPU cores, I/O stats
- **Network traffic** and **disk usage** in real-time

## 📊 **ATTACK PATTERNS**

### 🎯 **Endpoint Targets**

The stress tests will hammer these endpoints:

- `/v1/auth/me` - User profile (most common)
- `/v1/auth/login` - Authentication
- `/v1/auth/refresh` - Token refresh
- `/v1/users/` - User management
- `/v1/roles/` - Role management
- `/v1/permissions/` - Permission management
- `/v1/groups/` - Group management
- `/v1/client_accounts/` - Client account management

### 🔥 **Attack Types**

#### **1. Burst Attacks**

- Send 20-50 requests in rapid succession
- 50ms intervals between bursts
- Random endpoint selection

#### **2. Memory Pressure**

- Large JSON payloads (5-50KB)
- Complex nested data structures
- Array-heavy requests

#### **3. Sustained Load**

- Continuous requests over extended periods
- Gradual user ramp-up
- Realistic user behavior simulation

#### **4. Authentication Stress**

- Rapid login/logout cycles
- Token refresh hammering
- Concurrent session management

## 🎛️ **CONFIGURATION**

### **Stress Test Levels**

| Level           | Users | Duration | RPS Target | Memory Pressure |
| --------------- | ----- | -------- | ---------- | --------------- |
| 🔥 Warmup       | 50    | 30s      | ~100       | Low             |
| 🔥🔥 Medium     | 200   | 2m       | ~400       | Medium          |
| 🔥🔥🔥 Hardcore | 500   | 5m       | ~1000      | High            |
| 💀 Extreme      | 1000  | 10m      | ~2000+     | **EXTREME**     |

### **Custom Configuration**

Edit `ddos_stress_test.py` to customize:

```python
config = StressTestConfig(
    max_concurrent_users=1000,    # Concurrent users
    requests_per_user=100,        # Requests per user
    test_duration_seconds=300,    # Test duration
    burst_size=50,                # Burst size
    burst_interval=0.05,          # Burst interval
    payload_size_kb=10,           # Payload size
    generate_large_payloads=True, # Memory pressure
    random_delays=True,           # Chaos engineering
    connection_drops=True         # Connection failures
)
```

## 📈 **RESULTS & ANALYSIS**

### **Real-time Monitoring**

- **CPU Usage** - Track system load
- **Memory Usage** - Monitor memory pressure
- **Response Times** - Track performance degradation
- **Error Rates** - Monitor failure rates
- **Requests/Second** - Track throughput

### **Generated Reports**

```
stress_test_results/
├── warmup_test_20231201_143022.html     # Locust HTML report
├── warmup_test_20231201_143022_stats.csv # Detailed statistics
├── hardcore_stress_20231201_143022.html  # HTML report
├── async_stress_20231201_143022.log      # Async test log
└── stress_test_summary_20231201_143022.md # Summary report
```

### **Performance Metrics**

- **Total Requests** - Number of requests executed
- **Success Rate** - Percentage of successful requests
- **Average Response Time** - Mean response time
- **95th Percentile** - Response time for 95% of requests
- **99th Percentile** - Response time for 99% of requests
- **Requests/Second** - Throughput measurement
- **Error Distribution** - Types and frequency of errors

## 🏆 **PERFORMANCE BENCHMARKS**

### **Enterprise Grade Targets**

- **Success Rate**: >95% under normal load
- **Response Time**: <500ms average
- **95th Percentile**: <1000ms
- **99th Percentile**: <2000ms
- **Throughput**: >1000 RPS
- **CPU Usage**: <80% under load
- **Memory Usage**: <80% under load

### **Stress Test Survival Criteria**

- **🏆 ENTERPRISE GRADE**: >95% success, <1s avg response
- **⚠️ ACCEPTABLE**: >80% success, <2s avg response
- **💥 NEEDS WORK**: <80% success or >2s avg response

## 🚨 **WARNING LEVELS**

### 🔥 **Warmup Test**

- **Safe** for development systems
- **Minimal** system impact
- **Good** for initial validation

### 🔥🔥 **Medium Stress**

- **Moderate** system load
- **May** cause temporary slowdown
- **Suitable** for staging environments

### 🔥🔥🔥 **Hardcore Stress**

- **Heavy** system punishment
- **Will** cause significant load
- **Production-like** stress levels

### 💀 **Extreme DDoS**

- **DANGER**: May crash your system
- **EXTREME** resource usage
- **Only** for robust production systems
- **BACKUP YOUR DATA** before running

## 🗄️ **DATABASE SEEDING REQUIREMENTS**

**⚠️ CRITICAL: You MUST seed the database before running stress tests!**

### **Why Seeding is Essential**

Without seeded data, stress tests will **fail** because:

- **🔐 No admin user** to authenticate with
- **👥 No test users** to create realistic load patterns
- **🏢 No client accounts** to test authorization under load
- **📊 No baseline data** to stress database queries

### **Seeding Process**

```bash
# 1. Foundation seeding (creates admin, roles, permissions)
python scripts/seed_test_environment.py

# 2. Realistic API-based seeding (creates companies, users, groups)
python scripts/seed_via_api.py
```

### **What Gets Created**

- **🏢 6 Client Accounts**: Test Organization, ACME, Tech Startup, GreenTech, MedCorp, RetailPlus
- **👤 20+ Users**: Platform admin, client admins, managers, employees across companies
- **👥 9 Groups**: Engineering teams, management teams, operational groups
- **🔐 Realistic Permissions**: Proper RBAC hierarchies for testing

### **Test Credentials**

Use these for manual testing or custom stress scenarios:

- **Platform Admin**: `admin@test.com` / `admin123`
- **GreenTech Admin**: `admin@greentech.com` / `greentech123`
- **MedCorp Admin**: `admin@medcorp.com` / `medcorp123`
- **RetailPlus Admin**: `admin@retailplus.com` / `retail123`
- **All other users**: Password matches company (e.g., `green123`, `med123`, `retail123`)

## 🐳 **CONTAINER RESOURCE CONSTRAINTS**

### **Production-Like Limits**

The stress tests run against **resource-constrained containers** to simulate realistic production environments:

**API Container:**

- **Memory**: 8GB limit, 2GB reserved
- **CPU**: 4 cores
- **Workers**: 4 uvicorn workers
- **File Descriptors**: 8192 soft, 16384 hard
- **Processes**: 500 limit

**MongoDB Container:**

- **Memory**: 4GB limit, 1GB reserved
- **CPU**: 2 cores
- **File Descriptors**: 16384 soft, 32768 hard
- **Processes**: 1000 limit

### **Why Resource Constraints Matter**

- **🎯 Realistic Testing**: Simulates actual production resource limits
- **💀 Find Breaking Points**: See where system chokes under pressure
- **📊 Performance Baseline**: Establish realistic performance expectations
- **🔍 Bottleneck Discovery**: Identify CPU vs memory vs I/O constraints

## 🛡️ **SAFETY MEASURES**

### **Before Running Tests**

1. **✅ Seed the database** (see above section)
2. **✅ Setup container constraints** (`./stress_test/setup_containers.sh`)
3. **Backup your database** (if important data exists)
4. **Close unnecessary applications**
5. **Monitor system resources**
6. **Have a recovery plan**

### **During Tests**

- **Monitor CPU/Memory usage**
- **Watch for system warnings**
- **Be ready to kill the test** (Ctrl+C)
- **Check disk space**

### **Emergency Stop**

```bash
# Kill all stress tests
pkill -f locust
pkill -f ddos_stress_test.py

# Or use Ctrl+C in the terminal
```

## 🎪 **ADVANCED USAGE**

### **Distributed Testing**

Run tests across multiple machines for **maximum destruction**:

```bash
# Machine 1 (Master)
locust -f stress_test/locust_ddos.py --host=http://target-server:8030 --master

# Machine 2-N (Workers)
locust -f stress_test/locust_ddos.py --host=http://target-server:8030 --worker --master-host=machine1-ip
```

### **Custom Attack Scenarios**

Create custom user classes in `locust_ddos.py`:

```python
class CustomAttacker(HttpUser):
    wait_time = between(0.1, 0.3)

    @task(10)
    def custom_attack_pattern(self):
        # Your custom attack logic here
        pass
```

### **CI/CD Integration**

Integrate stress tests into your pipeline:

```yaml
# .github/workflows/stress-test.yml
- name: Run Stress Tests
  run: |
    ./stress_test/run_stress_tests.sh
    # Parse results and fail if performance degrades
```

## 🔧 **TROUBLESHOOTING**

### **Common Issues**

#### **"Connection refused"**

- **Solution**: Make sure your API is running on the correct port
- **Check**: `curl http://localhost:8030/docs`

#### **"Too many open files"**

- **Solution**: Increase file descriptor limits
- **Command**: `ulimit -n 65536`

#### **High memory usage**

- **Solution**: Reduce `payload_size_kb` or `max_concurrent_users`
- **Monitor**: `htop` or Activity Monitor

#### **Database connection errors**

- **Solution**: Increase MongoDB connection pool size
- **Config**: Update `motor` settings in your API

### **Performance Tuning**

#### **For Better Performance**

```python
# Increase connection pool
connector = aiohttp.TCPConnector(
    limit=2000,
    limit_per_host=1000
)

# Use uvloop
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
```

#### **For System Stability**

- Reduce concurrent users gradually
- Increase wait times between requests
- Monitor system resources continuously

## 📚 **DEPENDENCIES**

```
locust==2.17.0          # Web-based load testing
httpx==0.25.2           # Async HTTP client
aiohttp==3.9.1          # Async HTTP framework
uvloop==0.19.0          # High-performance event loop
psutil==5.9.6           # System monitoring
faker==20.1.0           # Test data generation
rich==13.7.0            # Beautiful terminal output
docker==6.1.3           # Docker container monitoring
```

## 🎉 **CONCLUSION**

This stress test suite will **absolutely destroy your system** with the most brutal load testing ever created. If your outlabsAuth system survives the **💀 Extreme DDoS test**, you can be confident it's ready for **enterprise production deployment**.

### **What Makes This Suite Special**

- **🐳 Production-like constraints**: 8GB RAM + 4 CPU cores for realistic testing
- **🗄️ Realistic data**: 20+ users across 6 companies with proper RBAC hierarchies
- **📊 Real-time monitoring**: Live container resource dashboard during attacks
- **🎯 Multiple attack vectors**: Web UI, async Python, orchestrated suites
- **⚡ Extreme performance**: 1000+ concurrent users with uvloop optimization

### **Pro Tips for Maximum Destruction**

1. **Run the monitor** (`python stress_test/monitor_container.py`) in a separate terminal
2. **Watch the resource dashboard** to see exactly when your system starts choking
3. **Use distributed testing** across multiple machines for ultimate DDoS simulation
4. **Start with warmup tests** and gradually increase to extreme levels
5. **Have fun watching your system suffer** under realistic enterprise load! 🔥

**Remember**: The goal is not to break your system, but to **find its limits** and ensure it can handle **real-world enterprise load** with grace and performance.

---

**🔥 HAPPY STRESS TESTING! MAY YOUR SYSTEM SURVIVE THE ASSAULT! 🔥**
