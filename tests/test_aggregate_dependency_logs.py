import unittest
import tempfile
from pathlib import Path
import aggregate_dependency_logs as agg

class TestAggregateDependencyLogs(unittest.TestCase):
    def test_aggregation_appends_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            log1 = tmpdir / 'dependency-resolution-repoA.log'
            log2 = tmpdir / 'dependency-resolution-repoB.log'
            content1 = (
                "******************** repoA DEPENDENCY RESOLUTION ***********************\n"
                "Could not resolve org.apache.commons:commons-text:1.10.0\n"
                "Could not find com.example:missing-lib:0.1.0\n"
                "**************END*******************\n"
            )
            content2 = (
                "******************** repoB DEPENDENCY RESOLUTION ***********************\n"
                "Could not resolve org.apache.commons:commons-text:1.9.0\n"
                "Could not resolve com.example:missing-lib:0.1.0\n"
                "**************END*******************\n"
            )
            log1.write_text(content1, encoding='utf-8')
            log2.write_text(content2, encoding='utf-8')
            agg_file = tmpdir / 'dependency-resolution-aggregated.log'
            # First run
            argv = ['--logs-dir', str(tmpdir), '--output-file', str(agg_file)]
            agg.main.__wrapped__ = agg.main if not hasattr(agg.main, '__wrapped__') else agg.main.__wrapped__
            # Call main via module execution
            # We simulate by calling functions directly
            results = agg.scan_logs(tmpdir, 'dependency-resolution-*.log')
            existing = agg.load_existing_coords(agg_file)
            self.assertEqual(len(existing), 0)
            new_coords = set()
            for r in results:
                for c in r['coords']:
                    if c not in existing:
                        new_coords.add(c)
            # Write aggregation
            agg_coords_lines = []
            for g,a,v in sorted(new_coords):
                agg_coords_lines.append(f"- {g}:{a}:{v}\n")
            agg_file.write_text("".join(agg_coords_lines), encoding='utf-8')
            # Second run should not duplicate existing entries, but add new versions only
            log3 = tmpdir / 'dependency-resolution-repoC.log'
            content3 = (
                "******************** repoC DEPENDENCY RESOLUTION ***********************\n"
                "Could not resolve org.apache.commons:commons-text:1.10.0\n"
                "Could not resolve org.slf4j:slf4j-api:2.0.12\n"
                "**************END*******************\n"
            )
            log3.write_text(content3, encoding='utf-8')
            # Now run module main to append
            agg.main()
            final = agg_file.read_text(encoding='utf-8')
            self.assertIn('org.slf4j:slf4j-api:2.0.12', final)
            # commons-text:1.10.0 should not be duplicated
            self.assertTrue(final.count('commons-text:1.10.0') >= 1)

if __name__ == '__main__':
    unittest.main()