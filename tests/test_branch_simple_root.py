#!/usr/bin/env python3
"""
Simple Test for Artifactory Plugin Branch Logic

This script tests the branch-based repository selection logic without requiring Gradle
"""

import tempfile
import subprocess
from pathlib import Path

def test_branch_detection():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, check=True)
        test_cases = [
            ('master', 'releases'),
            ('main', 'releases'),
            ('develop', 'snapshots'),
            ('feature/test', 'snapshots'),
            ('release/1.0', 'snapshots')
        ]
        print("Testing git branch detection:")
        print("=" * 40)
        for branch, expected_repo in test_cases:
            try:
                subprocess.run(['git', 'checkout', '-b', branch], cwd=temp_dir, check=True, capture_output=True)
                result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=temp_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    current_branch = result.stdout.strip()
                    target_repo = 'releases' if current_branch in ('master','main') else 'snapshots'
                    print(f"{'✅' if target_repo == expected_repo else '❌'} {branch} -> {expected_repo}")
                else:
                    print(f"❌ {branch} -> Could not detect branch")
            except subprocess.CalledProcessError:
                print(f"❌ {branch} -> Could not create branch")

def test_plugin_content():
    plugin_file = Path('templates/artifactory.gradle')
    if not plugin_file.exists():
        print("❌ Plugin template not found")
        return
    content = plugin_file.read_text()
    print("\nPlugin content validation:")
    print("=" * 30)
    checks = [
        ('Has branchName ext', 'branchName'),
        ('Release branch picks releases', 'artifactoryRepoName = isReleaseBranch ? "releases" : "snapshots"'),
        ('Git command rev-parse', 'git rev-parse --abbrev-ref HEAD'),
        ('Publishing configuration present', 'publishing {'),
        ('Artifactory block present', 'artifactory {')
    ]
    for check_name, pattern in checks:
        print(f"{'✅' if pattern in content else '❌'} {check_name}")

if __name__ == '__main__':
    print("Artifactory Plugin Branch Logic Test (Simple)")
    print("=" * 40)
    test_branch_detection()
    test_plugin_content()
    print("\nTest completed!")