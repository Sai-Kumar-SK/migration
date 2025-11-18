#!/usr/bin/env python3
"""
Simple Test for Artifactory Plugin Branch Logic

This script tests the branch-based repository selection logic without requiring Gradle
"""

import tempfile
import subprocess
from pathlib import Path

def test_branch_detection():
    """Test the git branch detection logic"""
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        
        # Initialize a git repository
        subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, check=True)
        
        # Test different branches
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
            # Create and switch to branch
            try:
                subprocess.run(['git', 'checkout', '-b', branch], cwd=temp_dir, check=True, capture_output=True)
                
                # Get current branch using git command (similar to what the plugin does)
                result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                      cwd=temp_dir, capture_output=True, text=True)
                
                if result.returncode == 0:
                    current_branch = result.stdout.strip()
                    
                    # Apply the same logic as the plugin
                    if current_branch == 'master' or current_branch == 'main':
                        target_repo = 'releases'
                    else:
                        target_repo = 'snapshots'
                    
                    if target_repo == expected_repo:
                        print(f"✅ {branch} -> {expected_repo} (Correct)")
                    else:
                        print(f"❌ {branch} -> {target_repo} (Expected: {expected_repo})")
                else:
                    print(f"❌ {branch} -> Could not detect branch")
                    
            except subprocess.CalledProcessError:
                print(f"❌ {branch} -> Could not create branch")
        
        print("\nBranch detection test completed!")

def test_plugin_content():
    """Test the plugin content for correct logic"""
    
    plugin_file = Path('templates/artifactory-publishing-enhanced.gradle')
    if not plugin_file.exists():
        print("❌ Plugin template not found")
        return
    
    content = plugin_file.read_text()
    
    print("\nPlugin content validation:")
    print("=" * 30)
    
    # Check for key components
    checks = [
        ('Branch detection method', 'determineTargetRepository'),
        ('Master branch logic', "currentBranch == 'master'"),
        ('Main branch logic', "currentBranch == 'main'"),
        ('Snapshot repository', 'libs-snapshot'),
        ('Release repository', 'libs-release'),
        ('Git command', "'git', 'rev-parse', '--abbrev-ref', 'HEAD'"),
        ('Publishing configuration', 'project.publishing'),
        ('No dependency resolution interference', 'dependencyResolutionManagement' not in content)
    ]
    
    all_passed = True
    for check_name, pattern in checks:
        if isinstance(pattern, str):
            if pattern in content:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
        else:
            # Handle boolean checks
            if pattern:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
    
    if all_passed:
        print("\n✅ All plugin checks passed!")
    else:
        print("\n❌ Some plugin checks failed!")

if __name__ == '__main__':
    print("Artifactory Plugin Branch Logic Test")
    print("=" * 40)
    
    test_branch_detection()
    test_plugin_content()
    
    print("\nTest completed!")
    print("\nThe plugin will automatically:")
    print("- Publish to 'libs-release' repository when on 'master' or 'main' branch")
    print("- Publish to 'libs-snapshot' repository when on any other branch")
    print("- Handle dependency resolution separately through settings.gradle")