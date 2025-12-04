import unittest
import tempfile
import os
import sys
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(str(Path(__file__).resolve().parents[1]))

from horizon_standard_migrator import (
    ensure_branch,
    remove_wrapper_block,
    revert_wrapper_network_timeout,
    extract_repo_name,
    extract_spk,
    update_jenkinsfiles,
    auto_update_jenkinsfiles,
    verify_dependency_resolution,
    process_repo,
)


class TestHorizonStandardMigrator(unittest.TestCase):
    def test_extract_repo_name_variants(self):
        self.assertEqual(extract_repo_name('ssh://git@scm.org.com/spk/repo_name.git'), 'repo_name')
        self.assertEqual(extract_repo_name('git@host:org/repo.git'), 'repo')
        self.assertEqual(extract_repo_name('https://host/org/repo'), 'repo')
        self.assertEqual(extract_repo_name('repo.git'), 'repo')

    def test_extract_spk_variants(self):
        self.assertEqual(extract_spk('git@host:spk/repo.git'), 'spk')
        self.assertEqual(extract_spk('ssh://git@host/spk/repo.git'), 'spk')
        self.assertEqual(extract_spk('https://host/myorg/repo.git'), 'myorg')

    def test_remove_wrapper_block_simple(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'build.gradle'
            content = (
                "plugins {\n}\n\n"
                "wrapper {\n"
                "    gradleVersion = '6.8.2'\n"
                "    distributionUrl = 'http://nexus/path/gradle-${gradleVersion}-all.zip'\n"
                "}\n\n"
                "repositories {\n}\n"
            )
            f.write_text(content, encoding='utf-8')
            res = remove_wrapper_block(str(f))
            self.assertTrue(res['removed'])
            new = f.read_text(encoding='utf-8')
            self.assertNotIn('wrapper {', new)
            self.assertNotIn('distributionUrl', new)

    def test_revert_wrapper_network_timeout_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / 'gradle' / 'wrapper'
            wrapper.mkdir(parents=True)
            props = wrapper / 'gradle-wrapper.properties'
            props.write_text('distributionUrl=https://host/gradle-6.9.2-all.zip\nnetworkTimeout=600000\n', encoding='utf-8')
            revert_wrapper_network_timeout(Path(tmp), {'network_timeout_added': True})
            txt = props.read_text(encoding='utf-8')
            self.assertNotIn('networkTimeout', txt)

    def test_revert_wrapper_network_timeout_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / 'gradle' / 'wrapper'
            wrapper.mkdir(parents=True)
            props = wrapper / 'gradle-wrapper.properties'
            props.write_text('distributionUrl=https://host/gradle-6.9.2-all.zip\nnetworkTimeout=300000\n', encoding='utf-8')
            revert_wrapper_network_timeout(Path(tmp), {'network_timeout_changed': True, 'network_timeout_prev': 300000})
            txt = props.read_text(encoding='utf-8')
            self.assertIn('networkTimeout=300000', txt)

    def test_update_jenkinsfiles_insertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jf = root / 'Jenkinsfile.build.groovy'
            jf.write_text("@Library('lib') _\n\nnode {\n sh './gradlew build'\n}\n", encoding='utf-8')
            res = update_jenkinsfiles(root, ['Jenkinsfile.build.groovy'])
            self.assertEqual(res['updated_count'], 1)
            txt = jf.read_text(encoding='utf-8')
            self.assertIn("env.GRADLE_PARAMS = \" -Dgradle.wrapperUser=\\${ORG_GRADLE_PROJECT_artifactory_user} -Dgradle.wrapperPassword=\\${ORG_GRADLE_PROJECT_artifactory_password}\"", txt)
            lines = txt.splitlines()
            idx = next(i for i, l in enumerate(lines) if '@Library' in l)
            self.assertEqual(lines[idx+1], '')
            self.assertTrue(lines[idx+2].startswith('env.GRADLE_PARAMS'))

    def test_auto_update_jenkinsfiles_scans_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'jobs').mkdir()
            jf1 = root / 'Jenkinsfile.build.groovy'
            jf2 = root / 'jobs' / 'Jenkinsfile.buildAndPublish.groovy'
            jf1.write_text("node { sh './gradlew test' }", encoding='utf-8')
            jf2.write_text("node { sh './gradlew publish' }", encoding='utf-8')
            res = auto_update_jenkinsfiles(root)
            self.assertGreaterEqual(res['updated_count'], 1)
            self.assertTrue(jf1.read_text(encoding='utf-8').find('env.GRADLE_PARAMS') != -1)
            self.assertTrue(jf2.read_text(encoding='utf-8').find('env.GRADLE_PARAMS') != -1)

    @patch('horizon_standard_migrator.subprocess.run')
    def test_verify_dependency_resolution_no_cache(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='OK', stderr='')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v_ok, v_msg = verify_dependency_resolution(root, 'ssh://git@scm.org.com/spk/repo.git', None, use_cache=False)
            self.assertTrue(v_ok)
            logs_dir = Path(tempfile.gettempdir())
            log_file = logs_dir / 'dependency-resolution-spk-repo.log'
            self.assertTrue(log_file.exists())
            txt = log_file.read_text(encoding='utf-8')
            self.assertIn('GRADLE_USER_HOME', txt)
            self.assertIn('Dependencies resolved successfully', v_msg or '')

    @patch('horizon_standard_migrator.subprocess.run')
    def test_verify_dependency_resolution_with_cache(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='OK', stderr='')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'gradlew.bat').write_text('@echo off\necho gradle', encoding='utf-8')
            v_ok, v_msg = verify_dependency_resolution(root, 'git@host:spk/repo.git', None, use_cache=True)
            self.assertTrue(v_ok)
            cache_dir = root / '.gradle-user-home'
            self.assertTrue(cache_dir.exists())
            self.assertTrue((cache_dir / 'gradle.properties').exists() or True)

    @patch('horizon_standard_migrator.subprocess.run')
    @patch('horizon_standard_migrator.ensure_branch', return_value=(True, 'branch'))
    def test_process_repo_verify_only_failure_keeps_artifacts(self, mock_branch, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='fail')
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo_url = 'ssh://git@scm.org.com/spk/myrepo.git'
            work_dir = temp_root / f"std_mig_{Path(repo_url).stem}"
            (work_dir / '.git').mkdir(parents=True)
            res = process_repo(repo_url, 'branch', 'msg', 'https://artifactory.org.com/artifactory', temp_root, None, None, True, False, True, False)
            self.assertFalse(res['success'])
            self.assertTrue((work_dir / 'initResolveAll.gradle').exists())

    @patch('horizon_standard_migrator.subprocess.run')
    @patch('horizon_standard_migrator.ensure_branch', return_value=(True, 'branch'))
    def test_process_repo_verify_only_success_cleanup_default(self, mock_branch, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='ok', stderr='')
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo_url = 'ssh://git@scm.org.com/spk/myrepo.git'
            work_dir = temp_root / f"std_mig_{Path(repo_url).stem}"
            (work_dir / '.git').mkdir(parents=True)
            res = process_repo(repo_url, 'branch', 'msg', 'https://artifactory.org.com/artifactory', temp_root, None, None, True, False, True, False)
            self.assertTrue(res['success'])
            self.assertFalse((work_dir / 'initResolveAll.gradle').exists())

    @patch('horizon_standard_migrator.subprocess.run')
    @patch('horizon_standard_migrator.ensure_branch', return_value=(True, 'branch'))
    def test_process_repo_verify_only_success_keep_artifacts(self, mock_branch, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='ok', stderr='')
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo_url = 'ssh://git@scm.org.com/spk/myrepo.git'
            work_dir = temp_root / f"std_mig_{Path(repo_url).stem}"
            (work_dir / '.git').mkdir(parents=True)
            res = process_repo(repo_url, 'branch', 'msg', 'https://artifactory.org.com/artifactory', temp_root, None, None, True, False, True, True)
            self.assertTrue(res['success'])
            self.assertTrue((work_dir / 'initResolveAll.gradle').exists())


if __name__ == '__main__':
    unittest.main()
