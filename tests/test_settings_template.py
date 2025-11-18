import unittest
import tempfile
from pathlib import Path
from settings_template import append_repositories_to_settings, get_settings_template

class TestSettingsTemplate(unittest.TestCase):
    def test_append_repositories_groovy(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.gradle'
            settings.write_text("rootProject.name='demo'")
            ok = append_repositories_to_settings(str(settings), "https://artifactory.org.com")
            self.assertTrue(ok)
            content = settings.read_text()
            self.assertIn('artifactory.org.com', content)

    def test_get_templates(self):
        groovy = get_settings_template(False)
        kts = get_settings_template(True)
        self.assertIn('repositories', groovy)
        self.assertIn('repositories', kts)

if __name__ == '__main__':
    unittest.main()