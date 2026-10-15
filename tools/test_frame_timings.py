"""Check timing statistics, host/GPU matching and failed-submission detection."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent/'regression'))
from benchmark import statistics, summarize


class Timings(unittest.TestCase):
    def test_percentiles_and_hitches(self):
        stats = statistics(list(range(1, 101)), 16)
        self.assertEqual((stats['median_ms'], stats['p95_ms'], stats['p99_ms']), (50, 95, 99))
        self.assertEqual(stats['over_budget'], 84)
        self.assertIsNone(statistics([]))

    def test_delayed_gpu_rows_and_failed_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'frames.csv'
            columns = 'kind,frame,interval_ms,fence_ms,acquire_ms,record_ms,submit_ms,present_ms,host_ms,submitted,shown,gpu_ms,scene_ms,upscale_ms,compile_ms,new_pipelines'.split(',')
            rows = []
            for kind, frame, time in [('host', 1, 100), ('host', 2, 5), ('gpu', 1, 100), ('gpu', 2, 2)]:
                row = dict.fromkeys(columns, 0)
                row.update(kind=kind, frame=frame, host_ms=time, gpu_ms=time, submitted=1)
                rows.append(row)
            def write():
                with path.open('w', newline='') as file:
                    writer = csv.DictWriter(file, columns)
                    writer.writeheader()
                    writer.writerows(rows)
            write()
            result = summarize(path, 1, 16)
            self.assertEqual(result['host']['host_ms']['median_ms'], 5)
            self.assertEqual(result['gpu']['gpu_ms']['median_ms'], 2)
            self.assertEqual(result['gpu_samples_missing'], 0)
            rows[-1]['frame'] = 3
            write()
            with self.assertRaisesRegex(ValueError, 'matching host'):
                summarize(path, 1, 16)
            rows[-1]['frame'] = 2
            rows[1]['submitted'] = 0
            write()
            with self.assertRaises(ValueError):
                summarize(path, 1, 16)


if __name__ == '__main__':
    unittest.main()
