import unittest
import tempfile
from pathlib import Path
from hzpublish_setup import HzPublishSetup

class TestHzPublishSetup(unittest.TestCase):
    def test_setup_and_copy_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            setup = HzPublishSetup(str(root))
            ok = setup.setup_buildsrc_structure()
            self.assertTrue(ok)
            src = Path(__file__).resolve().parents[1] / 'templates' / 'artifactory.gradle'
            copy_ok = setup.copy_artifactory_plugin(str(src))
            self.assertTrue(copy_ok)
            self.assertTrue(setup.create_hzpublish_plugin_class())
            verify = setup.verify_hzpublish_setup()
            self.assertTrue(verify['all_good'])

if __name__ == '__main__':
    unittest.main()