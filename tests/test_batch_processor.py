import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import batch_processor

class TestBatchProcessor(unittest.TestCase):
    def test_process_batch_invokes_enhanced_migrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            repos_file = Path(tmp) / 'repos.txt'
            repos_file.write_text('git@github.com:org/repo1.git\n')
            repos = batch_processor.load_repositories_from_file(str(repos_file))
            with patch('subprocess.run') as mock_run:
                mock_run.returncode = 0
                batch_processor.process_batch(repos, 1, {}, 'msg')
                self.assertTrue(mock_run.called)

if __name__ == '__main__':
    unittest.main()