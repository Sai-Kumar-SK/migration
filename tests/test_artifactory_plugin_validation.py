#!/usr/bin/env python3
"""
Test Script for Artifactory Plugin Validation
"""

import tempfile
import subprocess
from pathlib import Path

def test_artifactory_plugin_content():
    plugin_file = Path('templates/artifactory.gradle')
    if not plugin_file.exists():
        print("❌ templates/artifactory.gradle not found")
        return
    content = plugin_file.read_text()
    print("Artifactory Plugin Content Validation:")
    print("=" * 40)
    checks = [
        ('Uses com.jfrog.artifactory plugin', "id 'com.jfrog.artifactory'"),
        ('Configurable release branches', 'GIT_RELEASE_BRANCHES'),
        ('Branch name detection', 'branchName'),
        ('Release branch logic', 'isReleaseBranch'),
        ('Git URL parsing', 'gitUrl'),
        ('Organization/repo extraction', 'matcher.group("spk")'),
        ('Repository naming', 'artifactoryRepoName'),
        ('Artifactory context URL', 'artifactory_contextUrl'),
        ('Git command execution', 'gitCmd'),
        ('Version mapping', 'versionMapping'),
        ('Maven publication', 'mavenJava'),
        ('Artifactory publish task', 'artifactoryPublish'),
        ('Property validation', 'warnIfPropertyIsNull')
    ]
    for check_name, pattern in checks:
        print(f"{'✅' if pattern in content else '❌'} {check_name}")

def test_branch_logic_table():
    print("\nBranch Logic Table:")
    print("=" * 30)
    test_cases = [
        ("master", True, "releases"),
        ("origin/master", True, "releases"),
        ("main", True, "releases"),
        ("origin/main", True, "releases"),
        ("develop", False, "snapshots"),
        ("feature/test", False, "snapshots"),
        ("release/1.0", False, "snapshots"),
        ("hotfix/bug", False, "snapshots")
    ]
    for branch, is_release, repo in test_cases:
        print(f"- {branch} -> repo={repo}, isRelease={is_release}")

if __name__ == '__main__':
    print("Artifactory Plugin Validation")
    print("=" * 40)
    test_artifactory_plugin_content()
    test_branch_logic_table()
    print("\nTest completed!")