# API Limit Testing Plan - Discover Real Boundaries

**Date:** 2025-11-17
**Goal:** Empirically determine actual KNMI EDR API limits through systematic testing
**Status:** 🧪 Ready to Execute

---

## 🎯 What We Need to Find Out

### 1. **Data Point Limit (Unknown)**
- Current assumption: ~376,000 (UNVERIFIED!)
- Reality: Unknown - not documented by KNMI
- Goal: Find the actual maximum through testing

### 2. **Concurrent Request Limit**
- Documented: 200 requests/second
- Goal: Verify we can actually achieve near 200 req/sec
- Goal: Find optimal concurrency level (100? 150? 200?)

### 3. **Time Range Limit**
- Can we request 1 year? 5 years? 10 years? 25 years?
- For single station? Multiple stations?

### 4. **Station Batch Limit**
- Can we request 10 stations? 20? 50? 70?
- Does it depend on time range?

---

## 🧪 Testing Strategy

### Phase 1: Find Maximum Data Points Per Request

**Test Series A: Single Station, Increasing Time Range**

Goal: Find maximum time range for 1 station with all 23 parameters

| Test | Stations | Time Range | Hours | Data Points | Expected Result |
|------|----------|------------|-------|-------------|-----------------|
| A1 | 1 | 1 month | 720 | 16,560 | ✅ Should work |
| A2 | 1 | 3 months | 2,160 | 49,680 | ✅ Should work |
| A3 | 1 | 6 months | 4,320 | 99,360 | ✅ Should work |
| A4 | 1 | 1 year | 8,760 | 201,480 | ❓ Test needed |
| A5 | 1 | 2 years | 17,520 | 402,960 | ❓ May hit limit |
| A6 | 1 | 5 years | 43,800 | 1,007,400 | ❓ Likely exceeds limit |
| A7 | 1 | 10 years | 87,600 | 2,014,800 | ❓ Likely exceeds limit |
| A8 | 1 | 25 years | 219,000 | 5,037,000 | ❓ Likely exceeds limit |

**Test Series B: Multiple Stations, Fixed Time Range (1 month)**

Goal: Find maximum number of stations for 1 month

| Test | Stations | Time Range | Hours | Data Points | Expected Result |
|------|----------|------------|-------|-------------|-----------------|
| B1 | 5 | 1 month | 720 | 82,800 | ✅ Known to work (v2) |
| B2 | 10 | 1 month | 720 | 165,600 | ✅ Should work |
| B3 | 20 | 1 month | 720 | 331,200 | ❓ Test needed |
| B4 | 30 | 1 month | 720 | 496,800 | ❓ May exceed limit |
| B5 | 50 | 1 month | 720 | 828,000 | ❓ Likely exceeds limit |
| B6 | 70 | 1 month | 720 | 1,159,200 | ❓ Likely exceeds limit |

**Test Series C: Multiple Stations, Increasing Time Range**

Goal: Find optimal station × time combinations

| Test | Stations | Time Range | Hours | Data Points | Expected Result |
|------|----------|------------|-------|-------------|-----------------|
| C1 | 10 | 1 year | 8,760 | 2,014,800 | ❓ Test this! |
| C2 | 10 | 6 months | 4,320 | 993,600 | ❓ Test this! |
| C3 | 10 | 3 months | 2,160 | 496,800 | ❓ Test this! |
| C4 | 20 | 1 month | 720 | 331,200 | ❓ Test this! |
| C5 | 30 | 2 weeks | 336 | 231,840 | ❓ Test this! |

### Phase 2: Find Optimal Concurrency

**Test Series D: Concurrent API Calls**

Goal: Verify we can achieve near 200 req/sec throughput

| Test | Concurrent Workers | Batch Size | Expected Throughput | Test Duration |
|------|-------------------|------------|---------------------|---------------|
| D1 | 10 | 50 calls | ~10 req/sec | 5 seconds |
| D2 | 25 | 50 calls | ~25 req/sec | 2 seconds |
| D3 | 50 | 100 calls | ~50 req/sec | 2 seconds |
| D4 | 100 | 100 calls | ~100 req/sec | 1 second |
| D5 | 150 | 100 calls | ~150 req/sec | 0.67 seconds |
| D6 | 200 | 100 calls | ~200 req/sec | 0.5 seconds |

**Metrics to track:**
- Actual requests per second achieved
- Error rate (429 Too Many Requests)
- Response times
- Memory usage

---

## 🛠️ Implementation: Test Script

### Test Script Structure

```python
"""
API Limit Testing Script

Tests KNMI EDR API to discover actual limits:
- Maximum data points per request
- Maximum concurrent requests
- Optimal batch configurations

Usage:
    python scripts/test_api_limits.py --test-series A
    python scripts/test_api_limits.py --test-series B
    python scripts/test_api_limits.py --test-series C
    python scripts/test_api_limits.py --test-series D
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import EDR_API_KEY, EDR_BASE_URL, EDR_COLLECTION, STATIONS

class APILimitTester:
    def __init__(self):
        self.headers = {"Authorization": EDR_API_KEY}
        self.results = []

    def test_single_request(
        self,
        station_ids: List[str],
        start_date: str,
        end_date: str
    ) -> Dict:
        """Test a single API request and measure response"""

        # Calculate expected data points
        start = datetime.fromisoformat(start_date.replace('Z', ''))
        end = datetime.fromisoformat(end_date.replace('Z', ''))
        hours = int((end - start).total_seconds() / 3600)
        expected_points = hours * len(station_ids) * 23  # 23 parameters

        # Build request
        location_param = ",".join(station_ids)
        url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{location_param}"
        params = {"datetime": f"{start_date}/{end_date}"}

        print(f"\n{'='*80}")
        print(f"Testing: {len(station_ids)} stations, {hours:,} hours")
        print(f"Expected data points: {expected_points:,}")
        print(f"Stations: {station_ids[:3]}{'...' if len(station_ids) > 3 else ''}")
        print(f"Date range: {start_date} to {end_date}")

        try:
            start_time = time.time()
            response = requests.get(url, params=params, headers=self.headers, timeout=120)
            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                response_size = len(response.content)

                # Count actual data points (if possible to extract)
                actual_points = self._count_data_points(data)

                result = {
                    'success': True,
                    'status_code': 200,
                    'stations': len(station_ids),
                    'hours': hours,
                    'expected_points': expected_points,
                    'actual_points': actual_points,
                    'response_size_bytes': response_size,
                    'response_time_sec': elapsed,
                    'error': None
                }

                print(f"✅ SUCCESS")
                print(f"   Response size: {response_size:,} bytes ({response_size/1024/1024:.2f} MB)")
                print(f"   Response time: {elapsed:.2f} seconds")
                print(f"   Actual data points: {actual_points:,}")

            else:
                result = {
                    'success': False,
                    'status_code': response.status_code,
                    'stations': len(station_ids),
                    'hours': hours,
                    'expected_points': expected_points,
                    'actual_points': 0,
                    'response_size_bytes': 0,
                    'response_time_sec': elapsed,
                    'error': response.text[:200]
                }

                print(f"❌ FAILED")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text[:200]}")

        except requests.exceptions.Timeout:
            result = {
                'success': False,
                'status_code': 0,
                'stations': len(station_ids),
                'hours': hours,
                'expected_points': expected_points,
                'actual_points': 0,
                'response_size_bytes': 0,
                'response_time_sec': 120,
                'error': 'Timeout after 120 seconds'
            }
            print(f"❌ TIMEOUT")

        except Exception as e:
            result = {
                'success': False,
                'status_code': 0,
                'stations': len(station_ids),
                'hours': hours,
                'expected_points': expected_points,
                'actual_points': 0,
                'response_size_bytes': 0,
                'response_time_sec': 0,
                'error': str(e)
            }
            print(f"❌ ERROR: {e}")

        self.results.append(result)
        return result

    def _count_data_points(self, data: Dict) -> int:
        """Attempt to count actual data points in response"""
        try:
            if data.get('type') == 'CoverageCollection':
                coverages = data.get('coverages', [])
                total = 0
                for coverage in coverages:
                    # Try to count ranges (timestamps)
                    domain = coverage.get('domain', {})
                    axes = domain.get('axes', {})
                    if 't' in axes:
                        t_values = axes['t'].get('values', [])
                        num_times = len(t_values)

                        # Count parameters
                        ranges = coverage.get('ranges', {})
                        num_params = len(ranges)

                        total += num_times * num_params

                return total
            return 0
        except:
            return 0

    def run_test_series_a(self):
        """Test Series A: Single station, increasing time range"""
        print("\n" + "="*80)
        print("TEST SERIES A: Single Station, Increasing Time Range")
        print("="*80)

        station_id = STATIONS['hupsel']['id']
        base_date = "2024-01-01T00:00:00Z"

        tests = [
            ("1 month", 1),
            ("3 months", 3),
            ("6 months", 6),
            ("1 year", 12),
            ("2 years", 24),
            ("5 years", 60),
            ("10 years", 120),
        ]

        for name, months in tests:
            start = datetime(2024, 1, 1)
            end = start + timedelta(days=months*30)  # Approximate

            result = self.test_single_request(
                [station_id],
                start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end.strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            if not result['success']:
                print(f"\n⚠️  LIMIT FOUND: Maximum appears to be less than {name}")
                break

            time.sleep(1)  # Be nice to the API

    def run_test_series_b(self):
        """Test Series B: Multiple stations, fixed time range (1 month)"""
        print("\n" + "="*80)
        print("TEST SERIES B: Multiple Stations, 1 Month")
        print("="*80)

        all_station_ids = [STATIONS[key]['id'] for key in STATIONS.keys()]
        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-01-31T23:59:59Z"

        station_counts = [5, 10, 20, 30, 50, 70]

        for count in station_counts:
            if count > len(all_station_ids):
                print(f"⚠️  Only {len(all_station_ids)} stations configured, skipping {count}")
                continue

            station_batch = all_station_ids[:count]

            result = self.test_single_request(
                station_batch,
                start_date,
                end_date
            )

            if not result['success']:
                print(f"\n⚠️  LIMIT FOUND: Maximum appears to be less than {count} stations for 1 month")
                break

            time.sleep(1)

    def run_test_series_c(self):
        """Test Series C: Various station × time combinations"""
        print("\n" + "="*80)
        print("TEST SERIES C: Station × Time Combinations")
        print("="*80)

        all_station_ids = [STATIONS[key]['id'] for key in list(STATIONS.keys())[:10]]

        tests = [
            ("10 stations × 1 year", 10, 365),
            ("10 stations × 6 months", 10, 180),
            ("10 stations × 3 months", 10, 90),
            ("20 stations × 1 month", 20, 30),
        ]

        for name, num_stations, days in tests:
            if num_stations > len(all_station_ids):
                continue

            station_batch = all_station_ids[:num_stations]
            start = datetime(2024, 1, 1)
            end = start + timedelta(days=days)

            result = self.test_single_request(
                station_batch,
                start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end.strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            if not result['success']:
                print(f"\n⚠️  Configuration too large: {name}")

            time.sleep(1)

    def run_test_series_d(self):
        """Test Series D: Concurrent requests"""
        print("\n" + "="*80)
        print("TEST SERIES D: Concurrent Request Testing")
        print("="*80)

        station_id = STATIONS['hupsel']['id']

        # Create 100 small requests (1 day each)
        test_requests = []
        base_date = datetime(2024, 1, 1)
        for i in range(100):
            start = base_date + timedelta(days=i)
            end = start + timedelta(days=1)
            test_requests.append({
                'stations': [station_id],
                'start': start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'end': end.strftime("%Y-%m-%dT%H:%M:%SZ")
            })

        worker_counts = [10, 25, 50, 100, 150, 200]

        for workers in worker_counts:
            print(f"\nTesting with {workers} concurrent workers...")

            start_time = time.time()
            success_count = 0
            error_count = 0

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = []
                for req in test_requests:
                    future = executor.submit(
                        self.test_single_request,
                        req['stations'],
                        req['start'],
                        req['end']
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    result = future.result()
                    if result['success']:
                        success_count += 1
                    else:
                        error_count += 1

            elapsed = time.time() - start_time
            actual_rate = len(test_requests) / elapsed

            print(f"\n📊 Results for {workers} workers:")
            print(f"   Total requests: {len(test_requests)}")
            print(f"   Success: {success_count}")
            print(f"   Errors: {error_count}")
            print(f"   Total time: {elapsed:.2f} seconds")
            print(f"   Actual rate: {actual_rate:.2f} req/sec")
            print(f"   Target rate: 200 req/sec")
            print(f"   Efficiency: {(actual_rate/200)*100:.1f}%")

            if error_count > len(test_requests) * 0.1:  # More than 10% errors
                print(f"\n⚠️  Too many errors at {workers} workers, consider this the limit")
                break

    def print_summary(self):
        """Print summary of all test results"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]

        print(f"\nTotal tests: {len(self.results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")

        if successful:
            max_points = max(r['expected_points'] for r in successful)
            print(f"\n✅ Maximum confirmed data points: {max_points:,}")

            # Find the largest successful configuration
            largest = max(successful, key=lambda r: r['expected_points'])
            print(f"   Configuration: {largest['stations']} stations × {largest['hours']:,} hours")
            print(f"   Response size: {largest['response_size_bytes']:,} bytes")
            print(f"   Response time: {largest['response_time_sec']:.2f} seconds")

        if failed:
            min_failed_points = min(r['expected_points'] for r in failed)
            print(f"\n❌ First failure at: {min_failed_points:,} data points")

            # Find the smallest failed configuration
            smallest_fail = min(failed, key=lambda r: r['expected_points'])
            print(f"   Configuration: {smallest_fail['stations']} stations × {smallest_fail['hours']:,} hours")
            print(f"   Error: {smallest_fail['error']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test KNMI EDR API limits")
    parser.add_argument(
        '--test-series',
        choices=['A', 'B', 'C', 'D', 'all'],
        required=True,
        help='Which test series to run'
    )

    args = parser.parse_args()

    tester = APILimitTester()

    if args.test_series in ['A', 'all']:
        tester.run_test_series_a()

    if args.test_series in ['B', 'all']:
        tester.run_test_series_b()

    if args.test_series in ['C', 'all']:
        tester.run_test_series_c()

    if args.test_series in ['D', 'all']:
        tester.run_test_series_d()

    tester.print_summary()


if __name__ == "__main__":
    main()
```

---

## 📋 Execution Plan

### Step 1: Run Test Series A (Single Station Time Range)
```bash
python scripts/test_api_limits.py --test-series A
```

**Expected outcome:** Discover maximum time range for single station

### Step 2: Run Test Series B (Multiple Stations)
```bash
python scripts/test_api_limits.py --test-series B
```

**Expected outcome:** Discover maximum number of stations for 1 month

### Step 3: Run Test Series C (Combinations)
```bash
python scripts/test_api_limits.py --test-series C
```

**Expected outcome:** Find optimal station × time trade-offs

### Step 4: Run Test Series D (Concurrency)
```bash
python scripts/test_api_limits.py --test-series D
```

**Expected outcome:** Determine optimal number of concurrent workers

### Step 5: Analyze Results
- Document actual limits found
- Calculate optimal batch configurations
- Design v3 based on real data

---

## 🎯 Expected Discoveries

### Scenario 1: High Limit (Best Case)
- Can request 1+ year per station
- Can batch 20+ stations
- **Impact:** Massively simplify orchestration (single call per station per year!)

### Scenario 2: Medium Limit (Our Current Assumption)
- ~376K data points (~2 months × 8 stations)
- **Impact:** v2 strategy is correct

### Scenario 3: Low Limit (Worst Case)
- Lower than 376K (e.g., 100K points)
- **Impact:** Need smaller batches, more API calls

### Scenario 4: No Limit (Unlikely but Possible)
- Can request entire 25 years × 70 stations in one call
- **Impact:** Ultimate simplification!

---

## ✅ Success Criteria

After testing, we should know:

1. ✅ **Exact data point limit** (or confirm there is none)
2. ✅ **Optimal batch size** (stations per request)
3. ✅ **Optimal chunk size** (time range per request)
4. ✅ **Maximum achievable concurrency** (workers without errors)
5. ✅ **Ultimate v3 configuration** based on real limits

---

**Next Step:** Create `scripts/test_api_limits.py` and run systematic tests!
