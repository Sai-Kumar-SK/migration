import unittest
import tempfile
from pathlib import Path
from nexus_remover import NexusRemover

class TestNexusRemover(unittest.TestCase):
    def test_remove_nexus_and_add_artifactory(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp) / 'build.gradle'
            build.write_text(
                "classpath 'com.bmuschko:gradle-nexus-plugin:2.3.1'\n" \
                + "ext { branchName='master'; uploadArchivesUrl='http://nexus.org.com'; nexusUsername='x'; nexusPassword='y' }\n" \
                + "apply plugin: 'com.bmuschko.nexus'\n" \
                + "nexus { sign=false; repositoryUrl=uploadArchivesUrl }\n" \
                + "wrapper { distributionUrl='http://nexus' }\n"
            )
            remover = NexusRemover()
            result = remover.process_root_build_gradle(str(build))
            self.assertTrue(result['nexus_removed'])
            content = build.read_text()
            self.assertIn("com.jfrog.artifactory", content)

if __name__ == '__main__':
    unittest.main()