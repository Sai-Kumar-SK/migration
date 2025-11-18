import unittest
import tempfile
import subprocess
from pathlib import Path
from enhanced_gradle_migrator import EnhancedGradleArtifactoryMigrator

class TestBranchCreation(unittest.TestCase):
    def test_ensure_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init'], cwd=root, check=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=root, check=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=root, check=True)
            (root / 'README.md').write_text('init')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m', 'init'], cwd=root, check=True)
            migrator = EnhancedGradleArtifactoryMigrator(artifactory_url='https://artifactory.org.com')
            ok, msg = migrator.ensure_branch(root, 'horizon-migration')
            self.assertTrue(ok)
            current = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=root, capture_output=True, text=True)
            self.assertEqual(current.stdout.strip(), 'horizon-migration')

if __name__ == '__main__':
    unittest.main()