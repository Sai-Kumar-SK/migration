import unittest
import tempfile
from pathlib import Path
from wrapper_updater import update_gradle_wrapper

class TestWrapperUpdater(unittest.TestCase):
    def test_update_with_version_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Path(tmp) / 'gradle-wrapper.properties'
            props.write_text(
                'distributionBase=GRADLE_USER_HOME\n'
                'distributionPath=wrapper/dists\n'
                'distributionUrl=http\://nexus.org.com\:8000/nexus/content/repositories/thirdparty/org/gradle/gradle/6.8.3/gradle-6.8.3-all.zip\n'
                'zipStoreBase=GRADLE_USER_HOME\n'
                'zipStorePath=wrapper/dists\n',
                encoding='utf-8'
            )
            res = update_gradle_wrapper(str(props), 'https://artifactory.org.com/artifactory')
            self.assertTrue(res['success'])
            content = props.read_text(encoding='utf-8')
            self.assertIn('gradle-6.8.3-all.zip', content)
            self.assertIn('https\://artifactory.org.com/artifactory/libs-release/com/baml/plat/gradle/wrapper', content)

    def test_update_without_version_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Path(tmp) / 'gradle-wrapper.properties'
            props.write_text(
                'distributionBase=GRADLE_USER_HOME\n'
                'distributionPath=wrapper/dists\n'
                'distributionUrl=http\://nexus.org.com\:8000/nexus/content/repositories/thirdparty/invalid/url\n'
                'zipStoreBase=GRADLE_USER_HOME\n'
                'zipStorePath=wrapper/dists\n',
                encoding='utf-8'
            )
            res = update_gradle_wrapper(str(props), 'https://artifactory.org.com/artifactory')
            self.assertFalse(res['success'])
            self.assertIn('Unable to extract Gradle version', ''.join(res['errors']))

if __name__ == '__main__':
    unittest.main()