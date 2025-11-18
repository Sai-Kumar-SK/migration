import unittest
import tempfile
from pathlib import Path
from gradle_migration_workflow import GradleMigrationWorkflow

class TestGradleMigrationWorkflow(unittest.TestCase):
    def test_standard_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text("rootProject.name='demo'")
            (root / 'build.gradle').write_text("classpath 'com.bmuschko:gradle-nexus-plugin:2.3.1'\napply plugin: 'com.bmuschko.nexus'\n")
            workflow = GradleMigrationWorkflow(str(root))
            tpl = Path(__file__).resolve().parents[1] / 'templates' / 'artifactory.gradle'
            res = workflow.run_migration_workflow(str(tpl))
            self.assertTrue(res['success'])
            self.assertTrue(res['summary']['overall_success'])

    def test_platform_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'settings.gradle').write_text("rootProject.name='demo'\ninclude 'app'")
            (root / 'gradle').mkdir()
            (root / 'gradle' / 'libs.versions.toml').write_text('[versions]\nplasmaGradlePlugins="1.0.0"\n[libraries]\n')
            (root / 'buildSrc').mkdir()
            (root / 'buildSrc' / 'build.gradle').write_text('dependencies { implementation libs.plugin.publishing-nexus }')
            workflow = GradleMigrationWorkflow(str(root))
            tpl = Path(__file__).resolve().parents[1] / 'templates' / 'artifactory.gradle'
            res = workflow.run_migration_workflow(str(tpl))
            self.assertTrue(res['success'])
            self.assertTrue(res['is_gradle_platform'])

if __name__ == '__main__':
    unittest.main()