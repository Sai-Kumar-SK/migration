import unittest
import tempfile
from pathlib import Path
from jenkinsfile_manager import JenkinsfileManager

class TestJenkinsfileManager(unittest.TestCase):
    def test_replace_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jf = root / 'Jenkinsfile'
            jf.write_text('pipeline {}')
            tpl = Path(__file__).resolve().parents[1] / 'templates' / 'Jenkinsfile.enhanced'
            manager = JenkinsfileManager(str(root))
            rep = manager.replace_jenkinsfile(str(tpl))
            self.assertTrue(rep['success'])
            (root / 'Jenkinsfile.build.groovy').write_text('')
            (root / 'Jenkinsfile.seed.groovy').write_text('')
            cl = manager.cleanup_jenkinsfile_groovy_files()
            self.assertTrue(cl['success'])
            self.assertEqual(len(cl['files_deleted']), 2)

if __name__ == '__main__':
    unittest.main()