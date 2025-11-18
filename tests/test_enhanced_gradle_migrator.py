import unittest
import tempfile
from pathlib import Path
from enhanced_gradle_migrator import EnhancedGradleArtifactoryMigrator

class TestEnhancedGradleMigrator(unittest.TestCase):
    def test_run_comprehensive_migration_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text("rootProject.name='demo'")
            (root / 'build.gradle').write_text("apply plugin: 'com.bmuschko.nexus'\n")
            migrator = EnhancedGradleArtifactoryMigrator(artifactory_url='https://artifactory.org.com')
            res = migrator.run_comprehensive_migration(root)
            self.assertTrue(res.success)

    def test_run_comprehensive_migration_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text("rootProject.name='demo'")
            (root / 'gradle').mkdir()
            (root / 'gradle' / 'libs.versions.toml').write_text('[versions]\nplasmaGradlePlugins="1.0.0"\n[libraries]\n')
            migrator = EnhancedGradleArtifactoryMigrator(artifactory_url='https://artifactory.org.com')
            res = migrator.run_comprehensive_migration(root)
            self.assertTrue(res.gradle_platform_detected)

if __name__ == '__main__':
    unittest.main()