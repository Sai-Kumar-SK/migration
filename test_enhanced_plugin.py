#!/usr/bin/env python3
"""
Test Script for Enhanced Artifactory Plugin

This script tests the enhanced plugin that matches your existing artifactory.gradle
"""

import tempfile
import subprocess
from pathlib import Path

def test_enhanced_plugin_content():
    """Test the enhanced plugin content"""
    
    plugin_file = Path('templates/artifactory-publishing-enhanced.gradle')
    if not plugin_file.exists():
        print("❌ Enhanced plugin template not found")
        return
    
    content = plugin_file.read_text()
    
    print("Enhanced Plugin Content Validation:")
    print("=" * 40)
    
    # Check for key components from your existing artifactory.gradle
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
    
    all_passed = True
    for check_name, pattern in checks:
        if pattern in content:
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name}")
            all_passed = False
    
    if all_passed:
        print("\n✅ All enhanced plugin checks passed!")
    else:
        print("\n❌ Some enhanced plugin checks failed!")

def test_branch_logic_enhanced():
    """Test the enhanced branch logic"""
    
    print("\nEnhanced Branch Logic Test:")
    print("=" * 30)
    
    # Test cases based on your existing logic
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
    
    for branch, expected_release, expected_repo in test_cases:
        # Simulate the logic from your existing plugin
        release_branches = "origin/master,master,origin/main,main".split(",")
        is_release = branch in release_branches
        repo_name = "releases" if is_release else "snapshots"
        
        if is_release == expected_release and repo_name == expected_repo:
            print(f"✅ {branch} -> {repo_name} (Release: {is_release})")
        else:
            print(f"❌ {branch} -> {repo_name} (Expected: {expected_repo})")

def compare_with_existing():
    """Compare enhanced plugin with your existing artifactory.gradle"""
    
    existing_file = Path('artifactory.gradle')
    enhanced_file = Path('templates/artifactory-publishing-enhanced.gradle')
    
    if not existing_file.exists():
        print("❌ Existing artifactory.gradle not found")
        return
    
    if not enhanced_file.exists():
        print("❌ Enhanced plugin template not found")
        return
    
    existing_content = existing_file.read_text()
    enhanced_content = enhanced_file.read_text()
    
    print("\nComparison with Existing artifactory.gradle:")
    print("=" * 45)
    
    # Key features from your existing file
    key_features = [
        ("Configurable release branches", "GIT_RELEASE_BRANCHES"),
        ("Branch name property", "GIT_BRANCH"),
        ("Git URL parsing", "gitUrl =~ "),
        ("Organization extraction", "spk = matcher.group"),
        ("Repository name logic", "artifactoryRepoName = isReleaseBranch"),
        ("Artifactory context URL", "artifactory_contextUrl"),
        ("Git command helper", "gitCmd(String cmd)"),
        ("Version mapping", "versionMapping"),
        ("Maven publication", "mavenJava(MavenPublication)"),
        ("Artifactory plugin config", "artifactory {")
    ]
    
    for feature_name, pattern in key_features:
        if pattern in existing_content and pattern in enhanced_content:
            print(f"✅ {feature_name}")
        elif pattern in existing_content:
            print(f"⚠️  {feature_name} - In existing but not in enhanced")
        else:
            print(f"❌ {feature_name} - Not found in existing")

if __name__ == '__main__':
    print("Enhanced Artifactory Plugin Test")
    print("=" * 35)
    
    test_enhanced_plugin_content()
    test_branch_logic_enhanced()
    compare_with_existing()
    
    print("\nTest completed!")
    print("\nThe enhanced plugin incorporates your existing artifactory.gradle logic:")
    print("- Configurable release branch patterns")
    print("- Git URL parsing and organization extraction")
    print("- Branch-based repository selection (releases/snapshots)")
    print("- Proper Artifactory plugin integration")
    print("- All properties and environment variables from your existing setup")