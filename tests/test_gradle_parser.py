import unittest
import tempfile
from pathlib import Path
from gradle_parser import GradleProjectParser

class TestGradleParser(unittest.TestCase):
    def test_parse_structure_and_platform_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'build.gradle').write_text('plugins { id "java" }')
            (root / 'settings.gradle').write_text("rootProject.name='demo'\ninclude 'app'")
            (root / 'app').mkdir()
            (root / 'app' / 'build.gradle').write_text('plugins { id "java" }')
            (root / 'gradle' / 'wrapper').mkdir(parents=True)
            (root / 'gradle' / 'wrapper' / 'gradle-wrapper.properties').write_text('distributionUrl=https://services.gradle.org')
            (root / 'gradle').mkdir(exist_ok=True)
            (root / 'gradle' / 'libs.versions.toml').write_text('[versions]\nplasmaGradlePlugins="1.0.0"\n[libraries]\n')
            parser = GradleProjectParser(str(root))
            files = parser.find_all_gradle_files()
            self.assertTrue(len(files) >= 2)
            is_platform = parser.detect_gradle_platform()
            self.assertTrue(is_platform)
            structure = parser.get_project_structure()
            self.assertTrue(structure['root_build_gradle'].endswith('build.gradle'))
            self.assertTrue(structure['settings_gradle'].endswith('settings.gradle'))
            self.assertEqual(structure['gradle_wrapper_properties'].endswith('gradle-wrapper.properties'), True)

if __name__ == '__main__':
    unittest.main()