#!/usr/bin/env python3
"""
Validation Script for Gradle Migration Tool

This script validates your setup before running the actual migration.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def check_python_version():
    """Check Python version compatibility"""
    print("Checking Python version...")
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def check_dependencies():
    """Check if required Python packages are installed"""
    print("\nChecking dependencies...")
    required_packages = ['git', 'requests', 'colorama', 'rich', 'click']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    return True

def check_git():
    """Check Git installation and SSH key setup"""
    print("\nChecking Git installation...")
    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
        else:
            print("❌ Git not found in PATH")
            return False
    except FileNotFoundError:
        print("❌ Git not found in PATH")
        return False
    
    # Check SSH key
    print("\nChecking SSH key setup...")
    ssh_dir = Path.home() / '.ssh'
    if (ssh_dir / 'id_rsa').exists() or (ssh_dir / 'id_ed25519').exists():
        print("✅ SSH key found")
        
        # Test SSH connection to GitHub
        print("Testing SSH connection to GitHub...")
        try:
            result = subprocess.run(
                ['ssh', '-T', 'git@github.com'], 
                capture_output=True, text=True, timeout=10
            )
            if "successfully authenticated" in result.stderr.lower():
                print("✅ SSH connection to GitHub successful")
                return True
            else:
                print("⚠️  SSH connection test inconclusive")
                print("You may need to manually test: ssh -T git@github.com")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("⚠️  Could not test SSH connection")
            return True
    else:
        print("❌ No SSH key found in ~/.ssh/")
        print("Please set up SSH keys for Git access")
        return False

def check_artifactory_config():
    """Check Artifactory configuration"""
    print("\nChecking Artifactory configuration...")
    required_vars = [
        'ARTIFACTORY_URL',
        'ARTIFACTORY_REPO_KEY',
        'ARTIFACTORY_USERNAME',
        'ARTIFACTORY_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:20]}...")
        else:
            print(f"❌ {var}: not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\nMissing environment variables: {', '.join(missing_vars)}")
        print("Set them in your shell or create a .env file")
        return False
    
    return True

def check_templates():
    """Check if template files exist"""
    print("\nChecking template files...")
    templates_dir = Path('templates')
    required_templates = [
        'artifactory-publishing.gradle',
        'Jenkinsfile.artifactory'
    ]
    
    missing_templates = []
    for template in required_templates:
        template_path = templates_dir / template
        if template_path.exists():
            print(f"✅ {template}")
        else:
            print(f"❌ {template} - not found")
            missing_templates.append(template)
    
    if missing_templates:
        print(f"\nMissing templates: {', '.join(missing_templates)}")
        return False
    
    return True

def test_migration_script():
    """Test the migration script syntax"""
    print("\nTesting migration script...")
    try:
        result = subprocess.run([
            sys.executable, 'gradle_artifactory_migrator.py', '--help'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Migration script syntax is valid")
            return True
        else:
            print("❌ Migration script has syntax errors")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error testing migration script: {e}")
        return False

def main():
    """Main validation function"""
    print("Gradle Migration Tool - Setup Validation")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Git Setup", check_git),
        ("Artifactory Config", check_artifactory_config),
        ("Templates", check_templates),
        ("Migration Script", test_migration_script)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ {check_name} - Error: {e}")
            print()
    
    print("=" * 50)
    print(f"Validation Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ All checks passed! Your setup is ready for migration.")
        print("\nNext steps:")
        print("1. Set up your Artifactory credentials as environment variables")
        print("2. Create a list of repositories to migrate")
        print("3. Run: python gradle_artifactory_migrator.py --help")
    else:
        print(f"\n❌ {total - passed} checks failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == '__main__':
    main()