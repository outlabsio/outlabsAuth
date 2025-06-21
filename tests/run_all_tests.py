#!/usr/bin/env python3
"""
Run All Tests for outlabsAuth

This script runs all test modules individually and provides a comprehensive summary.
Can be run with: python tests/run_all_tests.py
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import json
import re

class TestResult:
    def __init__(self, module: str, passed: int, failed: int, skipped: int, duration: float, output: str = ""):
        self.module = module
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.duration = duration
        self.output = output
        self.total = passed + failed + skipped
    
    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100

class TestOrchestrator:
    def __init__(self):
        self.results: List[TestResult] = []
        self.test_modules = [
            "tests/test_auth_routes.py",
            "tests/test_auth_security.py",
            "tests/test_auth_comprehensive.py",
            "tests/test_user_routes.py", 
            "tests/test_role_routes.py",
            "tests/test_permission_routes.py",
            "tests/test_group_routes.py",
            "tests/test_group_service.py",
            "tests/test_client_account_routes.py",
            "tests/test_security_service.py",
            "tests/test_user_service.py",
            "tests/test_access_control.py",
            "tests/test_duplicate_constraints.py",
            "tests/test_integration.py",
            "tests/test_enhanced_access_control.py"
        ]
    
    def run_single_test_module(self, module_path: str) -> TestResult:
        """Run a single test module and parse results."""
        print(f"\n🧪 Running {module_path}...")
        
        start_time = time.time()
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                module_path, 
                "-v", 
                "--tb=short",
                "--no-header"
            ], capture_output=True, text=True, timeout=120)
            
            duration = time.time() - start_time
            output = result.stdout + result.stderr
            
            # Parse pytest output to extract test counts
            passed, failed, skipped = self._parse_pytest_output(output)
            
            test_result = TestResult(
                module=module_path,
                passed=passed,
                failed=failed, 
                skipped=skipped,
                duration=duration,
                output=output
            )
            
            status = "✅ PASSED" if failed == 0 else "❌ FAILED"
            print(f"   {status} - {passed} passed, {failed} failed, {skipped} skipped ({duration:.2f}s)")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"   ⏰ TIMEOUT after {duration:.2f}s")
            return TestResult(module_path, 0, 1, 0, duration, "Test timed out")
        except Exception as e:
            duration = time.time() - start_time
            print(f"   💥 ERROR: {str(e)}")
            return TestResult(module_path, 0, 1, 0, duration, f"Error: {str(e)}")
    
    def _parse_pytest_output(self, output: str) -> Tuple[int, int, int]:
        """Parse pytest output to extract test counts."""
        passed = failed = skipped = 0
        
        # Look for the summary line like "===== 3 passed, 1 failed, 2 skipped in 0.75s ======"
        lines = output.split('\n')
        for line in lines:
            if 'passed' in line or 'failed' in line or 'skipped' in line:
                if line.strip().startswith('=') and line.strip().endswith('='):  # Summary line
                    # Extract numbers before keywords
                    
                    # Find passed count
                    passed_match = re.search(r'(\d+)\s+passed', line)
                    if passed_match:
                        passed = int(passed_match.group(1))
                    
                    # Find failed count
                    failed_match = re.search(r'(\d+)\s+failed', line)
                    if failed_match:
                        failed = int(failed_match.group(1))
                    
                    # Find skipped count
                    skipped_match = re.search(r'(\d+)\s+skipped', line)
                    if skipped_match:
                        skipped = int(skipped_match.group(1))
                    
                    break
        
        return passed, failed, skipped
    
    def run_all_tests(self) -> None:
        """Run all test modules and collect results."""
        print("🚀 Starting Test Orchestration")
        print("=" * 60)
        
        start_time = time.time()
        
        for module in self.test_modules:
            # Skip modules that don't exist yet
            if not Path(module).exists():
                print(f"\n⚠️  Skipping {module} (file not found)")
                continue
                
            result = self.run_single_test_module(module)
            self.results.append(result)
        
        total_duration = time.time() - start_time
        self._print_summary(total_duration)
        self._save_report()
    
    def _print_summary(self, total_duration: float) -> None:
        """Print comprehensive test summary."""
        print("\n" + "=" * 60)
        print("📊 TEST ORCHESTRATION SUMMARY")
        print("=" * 60)
        
        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_skipped = sum(r.skipped for r in self.results)
        total_tests = total_passed + total_failed + total_skipped
        
        print(f"🕐 Total Duration: {total_duration:.2f}s")
        print(f"📁 Modules Run: {len(self.results)}")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {total_passed}")
        print(f"❌ Failed: {total_failed}")
        print(f"⏭️  Skipped: {total_skipped}")
        
        if total_tests > 0:
            success_rate = (total_passed / total_tests) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        print("\n📋 MODULE BREAKDOWN:")
        print("-" * 60)
        
        for result in self.results:
            status_icon = "✅" if result.failed == 0 else "❌"
            module_name = Path(result.module).stem
            print(f"{status_icon} {module_name:<25} "
                  f"P:{result.passed:>2} F:{result.failed:>2} S:{result.skipped:>2} "
                  f"({result.success_rate:>5.1f}%) {result.duration:>6.2f}s")
        
        if total_failed > 0:
            print(f"\n⚠️  {total_failed} test(s) failed. Check individual module outputs above.")
        else:
            print(f"\n🎉 All tests passed! Great job!")
        
        print("=" * 60)
    
    def _save_report(self) -> None:
        """Save detailed report to JSON file."""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_modules": len(self.results),
                "total_passed": sum(r.passed for r in self.results),
                "total_failed": sum(r.failed for r in self.results),
                "total_skipped": sum(r.skipped for r in self.results),
                "total_duration": sum(r.duration for r in self.results)
            },
            "modules": [
                {
                    "module": result.module,
                    "passed": result.passed,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "duration": result.duration,
                    "success_rate": result.success_rate
                }
                for result in self.results
            ]
        }
        
        report_path = Path("test_report.json")
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"📄 Detailed report saved to: {report_path}")

def main():
    """Main entry point for running all tests."""
    orchestrator = TestOrchestrator()
    orchestrator.run_all_tests()

if __name__ == "__main__":
    main() 