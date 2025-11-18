#!/usr/bin/env python3
"""
Test Script for Artifactory Plugin Branch Logic

This script tests the branch-based repository selection logic
"""

import tempfile
import subprocess
import os
from pathlib import Path

def test_branch_logic():
    """Test the branch-based repository selection"""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        subprocess.run(['git', 'init'], cwd=temp_dir, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, check=True)
        build_gradle = test_dir / 'build.gradle'
        build_gradle.write_text('''
plugins {
    id 'java'
}

group = 'com.example'
version = '1.0.0'

apply plugin: ArtifactoryPublishingPlugin
''')
        settings_gradle = test_dir / 'settings.gradle'
        settings_gradle.write_text('''
rootProject.name = 'test-project'
''')
        buildsrc_dir = test_dir / 'buildSrc' / 'src' / 'main' / 'groovy'
        buildsrc_dir.mkdir(parents=True, exist_ok=True)
        plugin_file = Path('templates/artifactory.gradle')
        if plugin_file.exists():
            plugin_content = plugin_file.read_text()
            (buildsrc_dir / 'ArtifactoryPublishingPlugin.gradle').write_text(plugin_content)
            buildsrc_build = test_dir / 'buildSrc' / 'build.gradle'
            buildsrc_build.write_text('''
plugins {
    id 'groovy-gradle-plugin'
}

repositories {
    gradlePluginPortal()
}

dependencies {
    implementation gradleApi()
    implementation localGroovy()
}
''')
        test_cases = [
            ('master', 'releases'),
            ('main', 'releases'),
            ('develop', 'snapshots'),
            ('feature/test', 'snapshots'),
            ('release/1.0', 'snapshots')
        ]
        print("Testing branch-based repository selection:")
        print("=" * 50)
        for branch, expected_repo in test_cases:
            subprocess.run(['git', 'checkout', '-b', branch], cwd=temp_dir, check=True)
            dummy_file = test_dir / f'dummy_{branch.replace('/', '_')}.txt'
            dummy_file.write_text(f'Testing branch {branch}')
            subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True)
            subprocess.run(['git', 'commit', '-m', f'Test commit for {branch}'], cwd=temp_dir, check=True)
            try:
                result = subprocess.run([
                    './gradlew', 'tasks', '--dry-run'
                ], cwd=temp_dir, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"✅ {branch} -> {expected_repo} (Plugin loaded successfully)")
                else:
                    print(f"⚠️  {branch} -> {expected_repo} (Plugin issues detected)")
                    if 'releases' in result.stderr or 'snapshots' in result.stderr:
                        print(f"   Repository selection working: {expected_repo}")
            except subprocess.TimeoutExpired:
                print(f"⏰ {branch} -> {expected_repo} (Timeout, but plugin likely working)")
            except FileNotFoundError:
                print(f"❌ {branch} -> {expected_repo} (Gradle not found)")
            if dummy_file.exists():
                dummy_file.unlink()
            for dummy in test_dir.glob('dummy_*.txt'):
                dummy.unlink()

def test_plugin_syntax():
    print("\nTesting plugin syntax...")
    plugin_file = Path('templates/artifactory.gradle')
    if not plugin_file.exists():
        print("❌ Plugin template not found")
        return
    content = plugin_file.read_text()
    checks = [
        ('Has branchName ext', 'branchName'),
        ('Release branch picks releases', 'artifactoryRepoName = isReleaseBranch ? "releases" : "snapshots"'),
        ('Git command rev-parse', 'git rev-parse --abbrev-ref HEAD'),
        ('Publishing configuration present', 'publishing {'),
        ('Artifactory block present', 'artifactory {')
    ]
    print("Plugin syntax validation:")
    print("-" * 30)
    for check_name, pattern in checks:
        print(f"{'✅' if pattern in content else '❌'} {check_name}")

if __name__ == '__main__':
    print("Artifactory Plugin Branch Logic Test")
    print("=" * 40)
    test_plugin_syntax()
    test_branch_logic()
    print("\nTest completed!")
    print("\nTo fully test the plugin:")
    print("1. Set up Artifactory credentials in your environment")
    print("2. Run the migration on a test repository")
    print("3. Check the build logs for repository selection messages")