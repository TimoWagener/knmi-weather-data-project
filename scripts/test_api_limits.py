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
    python scripts/test_api_limits.py --test-series all
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import requests
import time
import json
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
        end_date: str,
        test_name: str = ""
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
        if test_name:
            print(f"Test: {test_name}")
        print(f"Testing: {len(station_ids)} stations, {hours:,} hours")
        print(f"Expected data points: {expected_points:,}")
        print(f"Stations: {station_ids[:3]}{'...' if len(station_ids) > 3 else ''}")
        print(f"Date range: {start_date} to {end_date}")

        try:
            start_time = time.time()
            response = requests.get(url, params=params, headers=self.headers, timeout=180)
            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                response_size = len(response.content)

                # Count actual data points (if possible to extract)
                actual_points = self._count_data_points(data)

                result = {
                    'test_name': test_name,
                    'success': True,
                    'status_code': 200,
                    'stations': len(station_ids),
                    'hours': hours,
                    'expected_points': expected_points,
                    'actual_points': actual_points,
                    'response_size_bytes': response_size,
                    'response_time_sec': round(elapsed, 2),
                    'error': None
                }

                print(f"✅ SUCCESS")
                print(f"   Response size: {response_size:,} bytes ({response_size/1024/1024:.2f} MB)")
                print(f"   Response time: {elapsed:.2f} seconds")
                if actual_points > 0:
                    print(f"   Actual data points: {actual_points:,}")

            else:
                result = {
                    'test_name': test_name,
                    'success': False,
                    'status_code': response.status_code,
                    'stations': len(station_ids),
                    'hours': hours,
                    'expected_points': expected_points,
                    'actual_points': 0,
                    'response_size_bytes': 0,
                    'response_time_sec': round(elapsed, 2),
                    'error': response.text[:200]
                }

                print(f"❌ FAILED")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text[:200]}")

        except requests.exceptions.Timeout:
            result = {
                'test_name': test_name,
                'success': False,
                'status_code': 0,
                'stations': len(station_ids),
                'hours': hours,
                'expected_points': expected_points,
                'actual_points': 0,
                'response_size_bytes': 0,
                'response_time_sec': 180,
                'error': 'Timeout after 180 seconds'
            }
            print(f"❌ TIMEOUT")

        except Exception as e:
            result = {
                'test_name': test_name,
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

        station_id = list(STATIONS.values())[0]['id']  # Use first station
        base_date = "2024-01-01T00:00:00Z"

        tests = [
            ("A1: 1 month", 1),
            ("A2: 3 months", 3),
            ("A3: 6 months", 6),
            ("A4: 1 year", 12),
            ("A5: 2 years", 24),
            ("A6: 5 years", 60),
            ("A7: 10 years", 120),
            ("A8: 25 years", 300),
        ]

        for name, months in tests:
            start = datetime(2024, 1, 1)
            end = start + timedelta(days=months*30)  # Approximate

            result = self.test_single_request(
                [station_id],
                start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                test_name=name
            )

            if not result['success']:
                print(f"\n⚠️  LIMIT FOUND: Maximum appears to be less than {name.split(':')[1].strip()}")
                break

            time.sleep(2)  # Be nice to the API

    def run_test_series_b(self):
        """Test Series B: Multiple stations, fixed time range (1 month)"""
        print("\n" + "="*80)
        print("TEST SERIES B: Multiple Stations, 1 Month")
        print("="*80)

        all_station_ids = [s['id'] for s in STATIONS.values()]
        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-01-31T23:59:59Z"

        station_counts = [5, 10, 15, 20, 30, 50, 70]

        for count in station_counts:
            if count > len(all_station_ids):
                print(f"⚠️  Only {len(all_station_ids)} stations configured, skipping {count}")
                continue

            station_batch = all_station_ids[:count]

            result = self.test_single_request(
                station_batch,
                start_date,
                end_date,
                test_name=f"B: {count} stations × 1 month"
            )

            if not result['success']:
                print(f"\n⚠️  LIMIT FOUND: Maximum appears to be less than {count} stations for 1 month")
                break

            time.sleep(2)

    def run_test_series_c(self):
        """Test Series C: Various station × time combinations"""
        print("\n" + "="*80)
        print("TEST SERIES C: Station × Time Combinations")
        print("="*80)

        all_station_ids = [s['id'] for s in list(STATIONS.values())[:10]]

        tests = [
            ("C1: 10 stations × 1 year", 10, 365),
            ("C2: 10 stations × 6 months", 10, 180),
            ("C3: 10 stations × 3 months", 10, 90),
            ("C4: 8 stations × 1 year", 8, 365),
            ("C5: 5 stations × 2 years", 5, 730),
        ]

        for name, num_stations, days in tests:
            if num_stations > len(all_station_ids):
                print(f"⚠️  Only {len(all_station_ids)} stations available, skipping {name}")
                continue

            station_batch = all_station_ids[:num_stations]
            start = datetime(2024, 1, 1)
            end = start + timedelta(days=days)

            result = self.test_single_request(
                station_batch,
                start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                test_name=name
            )

            if not result['success']:
                print(f"\n⚠️  Configuration too large: {name}")

            time.sleep(2)

    def run_test_series_d(self):
        """Test Series D: Concurrent requests"""
        print("\n" + "="*80)
        print("TEST SERIES D: Concurrent Request Testing")
        print("="*80)

        station_id = list(STATIONS.values())[0]['id']

        # Create 50 small requests (1 day each) for faster testing
        test_requests = []
        base_date = datetime(2024, 1, 1)
        for i in range(50):
            start = base_date + timedelta(days=i)
            end = start + timedelta(days=1)
            test_requests.append({
                'stations': [station_id],
                'start': start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'end': end.strftime("%Y-%m-%dT%H:%M:%SZ")
            })

        worker_counts = [10, 25, 50, 100]

        for workers in worker_counts:
            print(f"\n{'='*80}")
            print(f"Testing with {workers} concurrent workers...")
            print(f"Total requests: {len(test_requests)}")

            start_time = time.time()
            success_count = 0
            error_count = 0
            results_list = []

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {}
                for i, req in enumerate(test_requests):
                    future = executor.submit(
                        self._quick_request,
                        req['stations'],
                        req['start'],
                        req['end']
                    )
                    futures[future] = i

                for future in as_completed(futures):
                    result = future.result()
                    results_list.append(result)
                    if result['success']:
                        success_count += 1
                    else:
                        error_count += 1
                        print(f"   Error on request {futures[future]}: {result['error'][:50]}")

            elapsed = time.time() - start_time
            actual_rate = len(test_requests) / elapsed

            print(f"\n📊 Results for {workers} workers:")
            print(f"   Success: {success_count}/{len(test_requests)}")
            print(f"   Errors: {error_count}")
            print(f"   Total time: {elapsed:.2f} seconds")
            print(f"   Actual rate: {actual_rate:.2f} req/sec")
            print(f"   Target rate: 200 req/sec")
            print(f"   Efficiency: {(actual_rate/200)*100:.1f}%")

            if error_count > len(test_requests) * 0.1:  # More than 10% errors
                print(f"\n⚠️  Too many errors at {workers} workers, consider this the limit")
                break

            time.sleep(5)  # Cooldown between tests

    def _quick_request(self, station_ids, start_date, end_date):
        """Quick request without logging (for concurrency tests)"""
        location_param = ",".join(station_ids)
        url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{location_param}"
        params = {"datetime": f"{start_date}/{end_date}"}

        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'error': None if response.status_code == 200 else response.text[:100]
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'error': str(e)
            }

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
            largest = max(successful, key=lambda r: r['expected_points'])

            print(f"\n✅ MAXIMUM CONFIRMED DATA POINTS: {max_points:,}")
            print(f"\nLargest successful configuration:")
            print(f"   Test: {largest['test_name']}")
            print(f"   Stations: {largest['stations']}")
            print(f"   Hours: {largest['hours']:,}")
            print(f"   Data points: {largest['expected_points']:,}")
            print(f"   Response size: {largest['response_size_bytes']:,} bytes ({largest['response_size_bytes']/1024/1024:.2f} MB)")
            print(f"   Response time: {largest['response_time_sec']:.2f} seconds")

        if failed:
            min_failed_points = min(r['expected_points'] for r in failed)
            smallest_fail = min(failed, key=lambda r: r['expected_points'])

            print(f"\n❌ FIRST FAILURE AT: {min_failed_points:,} data points")
            print(f"\nSmallest failed configuration:")
            print(f"   Test: {smallest_fail['test_name']}")
            print(f"   Stations: {smallest_fail['stations']}")
            print(f"   Hours: {smallest_fail['hours']:,}")
            print(f"   Data points: {smallest_fail['expected_points']:,}")
            print(f"   Error: {smallest_fail['error']}")

        # Save results to JSON
        output_file = Path(__file__).parent.parent / 'logs' / f'api_limits_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📄 Full results saved to: {output_file}")


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

    print("\n" + "="*80)
    print("KNMI EDR API LIMIT TESTING")
    print("="*80)
    print(f"\nAPI Endpoint: {EDR_BASE_URL}")
    print(f"Collection: {EDR_COLLECTION}")
    print(f"Stations configured: {len(STATIONS)}")
    print(f"\nTest series: {args.test_series}")

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
