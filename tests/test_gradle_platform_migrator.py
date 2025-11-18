import unittest
import tempfile
from pathlib import Path
from gradle_platform_migrator import GradlePlatformMigrator

class TestGradlePlatformMigrator(unittest.TestCase):
    def test_libs_versions_and_buildsrc_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'gradle').mkdir(parents=True, exist_ok=True)
            libs = (root / 'gradle' / 'libs.versions.toml')
            libs.write_text('[versions]\nplasmaGradlePlugins="1.0.0"\n[libraries]\n' \
                            + 'plugin-publishing-nexus = { module = "ops.plasma.publishing-nexus:ops.plasma.publishing-nexus.gradle.plugin", versions.ref = "plasmaGradlePlugins" }\n' \
                            + 'plugin-repositories-nexus = { module = "ops.plasma.repositories-nexus:ops.plasma.repositories-nexus.gradle.plugin", versions.ref = "plasmaGradlePlugins" }\n')
            (root / 'buildSrc').mkdir()
            buildsrc = root / 'buildSrc' / 'build.gradle'
            buildsrc.write_text('dependencies {\n    implementation libs.plugin.publishing-nexus\n    implementation libs.plugin.repositories-nexus\n}\n')
            settings = root / 'settings.gradle'
            settings.write_text("rootProject.name='demo'\ninclude 'app'")
            migrator = GradlePlatformMigrator(str(root))
            res_libs = migrator.update_libs_versions_toml()
            self.assertTrue(res_libs['success'])
            text_libs = libs.read_text()
            self.assertIn('plugin-publishing-artifactory', text_libs)
            self.assertIn('plugin-repositories-artifactory', text_libs)
            self.assertNotIn('plugin-publishing-nexus', text_libs)
            self.assertNotIn('plugin-repositories-nexus', text_libs)
            res_buildsrc = migrator.update_buildsrc_build_gradle()
            self.assertTrue(res_buildsrc['success'])
            text_buildsrc = buildsrc.read_text()
            self.assertIn('publishing-artifactory', text_buildsrc)
            self.assertIn('repositories-artifactory', text_buildsrc)
            res_settings = migrator.validate_root_settings_gradle()
            self.assertTrue(res_settings['valid'])

    def test_buildsrc_settings_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'buildSrc').mkdir()
            (root / 'buildSrc' / 'settings.gradle').write_text('rootProject.name="buildSrc"')
            migrator = GradlePlatformMigrator(str(root))
            res = migrator.check_buildsrc_settings_gradle()
            self.assertTrue(res['exists'])

if __name__ == '__main__':
    unittest.main()