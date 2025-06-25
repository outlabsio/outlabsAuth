#!/usr/bin/env python3
"""
Run All Tests for outlabsAuth - Enterprise Production Readiness Validation

🏢 ENTERPRISE-LEVEL TESTING SUITE 🏢
Comprehensive validation for production-ready RBAC microservice

Current Status: 68.7% Success Rate (189/275 tests)
Target: 100% Bulletproof Coverage for Enterprise Production

🎯 PHASE 1 OBJECTIVES (Target: 85% Success Rate):
- ✅ Core authentication & authorization flows
- ✅ Multi-tenant data isolation & security boundaries  
- ✅ Permission system with detailed object format
- 🔄 Complete PropertyHub three-tier scenario coverage
- 🔄 Fix remaining permission format compatibility issues

🏆 PRODUCTION READY MODULES (100% Success):
- Authentication Routes (40/40) - Login, logout, session management
- Permission Routes (10/10) - CRUD operations and validation
- Client Account Routes (14/14) - Multi-tenant account management
- Security Service (15/15) - JWT, encryption, token validation
- User Service (13/13) - User management and effective permissions

⚠️ ENTERPRISE HARDENING REQUIRED:
- Access Control (0/6) - Core security boundary validation
- Role Routes (2/14) - Role-based permission assignment
- Performance Testing - Load testing under enterprise traffic
- Security Testing - Penetration testing and vulnerability scanning
- Compliance Testing - GDPR, SOC2, audit trail validation

This script runs all test modules individually and provides comprehensive 
enterprise-level reporting for production readiness assessment.

Usage:
    python tests/run_all_tests.py
    
Can be run from project root or tests directory.
Generates detailed JSON report: test_report.json
"""

import subprocess
import time
import sys
import json
from pathlib import Path
from datetime import datetime

def find_project_root():
    """Find the project root directory."""
    current = Path.cwd()
    
    # Check if we're in the tests directory
    if current.name == "tests":
        return current.parent
    
    # Check if we're in the project root (has api directory)
    if (current / "api").exists():
        return current
    
    # Look for parent directories with api
    for parent in current.parents:
        if (parent / "api").exists():
            return parent
    
    raise FileNotFoundError("Could not find project root directory")

def run_test_module(module_path):
    """Run a single test module and return results."""
    start_time = time.time()
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", str(module_path), "-v", "--tb=short"
        ], capture_output=True, text=True, timeout=120)
        
        duration = time.time() - start_time
        
        # Parse pytest output for counts
        output_lines = result.stdout.split('\n')
        summary_line = None
        for line in reversed(output_lines):
            if "passed" in line or "failed" in line or "error" in line:
                if any(word in line for word in ["passed", "failed", "error", "skipped"]):
                    summary_line = line
                    break
        
        # Extract counts from summary
        passed = failed = skipped = 0
        if summary_line:
            import re
            passed_match = re.search(r'(\d+) passed', summary_line)
            failed_match = re.search(r'(\d+) failed', summary_line)
            skipped_match = re.search(r'(\d+) skipped', summary_line)
            
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            skipped = int(skipped_match.group(1)) if skipped_match else 0
        
        # Determine status
        if result.returncode == 0 and failed == 0:
            status = "PASSED"
        else:
            status = "FAILED"
        
        return {
            "module": module_path.stem,
            "status": status,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": duration,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    except subprocess.TimeoutExpired:
        return {
            "module": module_path.stem,
            "status": "TIMEOUT",
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "duration": 120.0,
            "return_code": -1,
            "stdout": "",
            "stderr": "Test timed out after 120 seconds"
        }
    except Exception as e:
        return {
            "module": module_path.stem,
            "status": "ERROR",
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "duration": time.time() - start_time,
            "return_code": -1,
            "stdout": "",
            "stderr": str(e)
        }

def main():
    """Run all tests and generate comprehensive report."""
    print("🚀 Starting Enterprise Test Orchestration")
    print("=" * 60)
    
    try:
        project_root = find_project_root()
        tests_dir = project_root / "tests"
        
        if not tests_dir.exists():
            print(f"❌ Tests directory not found: {tests_dir}")
            return 1
        
        # Find all test modules
        test_modules = list(tests_dir.glob("test_*.py"))
        test_modules.sort()
        
        if not test_modules:
            print(f"❌ No test modules found in {tests_dir}")
            return 1
        
        all_results = []
        total_start_time = time.time()
        
        # Run each test module
        for module_path in test_modules:
            print(f"\n🧪 Running {module_path.name}...")
            result = run_test_module(module_path)
            all_results.append(result)
            
            # Display immediate result
            status_icon = "✅" if result["status"] == "PASSED" else "❌"
            print(f"   {status_icon} {result['status']} - {result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped ({result['duration']:.2f}s)")
        
        total_duration = time.time() - total_start_time
        
        # Calculate summary statistics
        total_modules = len(all_results)
        passed_modules = sum(1 for r in all_results if r["status"] == "PASSED")
        failed_modules = total_modules - passed_modules
        
        total_tests = sum(r["passed"] + r["failed"] + r["skipped"] for r in all_results)
        total_passed = sum(r["passed"] for r in all_results)
        total_failed = sum(r["failed"] for r in all_results)
        total_skipped = sum(r["skipped"] for r in all_results)
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Print comprehensive summary
        print("\n" + "=" * 60)
        print("📊 ENTERPRISE TEST ORCHESTRATION SUMMARY")
        print("=" * 60)
        print(f"🕐 Total Duration: {total_duration:.2f}s")
        print(f"📁 Modules Run: {total_modules}")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {total_passed}")
        print(f"❌ Failed: {total_failed}")
        print(f"⏭️  Skipped: {total_skipped}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        # Enterprise production readiness assessment
        print(f"\n🏢 ENTERPRISE PRODUCTION READINESS ASSESSMENT:")
        if success_rate >= 95:
            print("🟢 PRODUCTION READY - Exceeds enterprise standards")
        elif success_rate >= 85:
            print("🟡 NEAR PRODUCTION READY - Minor hardening required")
        elif success_rate >= 70:
            print("🟠 DEVELOPMENT READY - Significant testing gaps remain")
        else:
            print("🔴 NOT PRODUCTION READY - Major stability issues")
        
        # Module breakdown
        print(f"\n📋 MODULE BREAKDOWN:")
        print("-" * 60)
        for result in all_results:
            success_pct = (result["passed"] / (result["passed"] + result["failed"]) * 100) if (result["passed"] + result["failed"]) > 0 else 0
            status_icon = "✅" if result["status"] == "PASSED" else "❌"
            print(f"{status_icon} {result['module']:<25} P:{result['passed']:>2} F:{result['failed']:>2} S:{result['skipped']:>2} ({success_pct:>5.1f}%) {result['duration']:>6.2f}s")
        
        # Identify critical failures
        critical_failures = [r for r in all_results if r["failed"] > 0]
        if critical_failures:
            print(f"\n⚠️  {len(critical_failures)} test module(s) failed. Check individual module outputs above.")
        
        # Generate detailed JSON report
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_duration": total_duration,
                "modules_run": total_modules,
                "modules_passed": passed_modules,
                "modules_failed": failed_modules,
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_skipped": total_skipped,
                "success_rate": success_rate
            },
            "modules": all_results,
            "enterprise_assessment": {
                "production_ready": success_rate >= 95,
                "near_production_ready": success_rate >= 85,
                "development_ready": success_rate >= 70,
                "critical_issues": len(critical_failures)
            }
        }
        
        report_path = project_root / "test_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("=" * 60)
        print(f"📄 Detailed report saved to: {report_path}")
        
        # Return appropriate exit code for CI/CD
        return 0 if total_failed == 0 else 1
        
    except Exception as e:
        print(f"❌ Test orchestration failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 