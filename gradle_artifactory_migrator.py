#!/usr/bin/env python3
"""
Gradle Nexus to Artifactory Migration Automation Script

This script automates the migration of Gradle projects from Nexus to Artifactory
by applying a custom publishing plugin and updating configuration files.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MigrationResult:
    """Result of a repository migration"""
    repo_url: str
    success: bool
    message: str
    changes: List[str]

class GradleArtifactoryMigrator:
    """Main class for handling Gradle to Artifactory migrations"""
    
    def __init__(self, artifactory_url: str, artifactory_repo_key: str, 
                 artifactory_username: str, artifactory_password: str,
                 max_workers: int = 10, temp_dir: Optional[str] = None):
        self.artifactory_url = artifactory_url
        self.artifactory_repo_key = artifactory_repo_key
        self.artifactory_username = artifactory_username
        self.artifactory_password = artifactory_password
        self.max_workers = max_workers
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # Setup logging
        self.setup_logging()
        
        # Load templates
        self.templates_dir = Path(__file__).parent / 'templates'
        self.plugin_template = self.load_template('artifactory-publishing.gradle')
        self.jenkinsfile_template = self.load_template('Jenkinsfile.artifactory')
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler('migration.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_template(self, template_name: str) -> str:
        """Load template file content"""
        template_path = self.templates_dir / template_name
        if template_path.exists():
            return template_path.read_text()
        else:
            self.logger.warning(f"Template {template_name} not found, using default")
            return self.get_default_template(template_name)
    
    def get_default_template(self, template_name: str) -> str:
        """Get default template content if file doesn't exist"""
        if template_name == 'Jenkinsfile.artifactory':
            return self.get_default_jenkinsfile()
        return ""
    
    def get_default_jenkinsfile(self) -> str:
        """Default Jenkinsfile template for Artifactory"""
        return '''
pipeline {
    agent any
    
    environment {
        ARTIFACTORY_URL = credentials('artifactory-url')
        ARTIFACTORY_REPO_KEY = credentials('artifactory-repo-key')
        ARTIFACTORY_USERNAME = credentials('artifactory-username')
        ARTIFACTORY_PASSWORD = credentials('artifactory-password')
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build') {
            steps {
                sh './gradlew clean build'
            }
        }
        
        stage('Test') {
            steps {
                sh './gradlew test'
            }
        }
        
        stage('Publish to Artifactory') {
            steps {
                sh """
                    ./gradlew publish \
                    -Partifactory.url=\${ARTIFACTORY_URL} \
                    -Partifactory.repoKey=\${ARTIFACTORY_REPO_KEY} \
                    -Partifactory.username=\${ARTIFACTORY_USERNAME} \
                    -Partifactory.password=\${ARTIFACTORY_PASSWORD}
                """
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}
'''
    
    def clone_repository(self, repo_url: str, commit_message: str) -> Tuple[Path, bool, str]:
        """Clone repository and create working directory"""
        try:
            # Extract repo name from URL
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            work_dir = Path(self.temp_dir) / f"{repo_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self.logger.info(f"Cloning {repo_url} to {work_dir}")
            
            # Clone repository
            result = subprocess.run([
                'git', 'clone', repo_url, str(work_dir)
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                return work_dir, False, f"Git clone failed: {result.stderr}"
            
            # Create new branch for migration
            subprocess.run([
                'git', '-C', str(work_dir), 'checkout', '-b', 'artifactory-migration'
            ], capture_output=True)
            
            return work_dir, True, "Repository cloned successfully"
            
        except subprocess.TimeoutExpired:
            return work_dir, False, "Git clone timed out"
        except Exception as e:
            return work_dir, False, f"Error cloning repository: {str(e)}"
    
    def create_publishing_plugin(self, work_dir: Path) -> Tuple[bool, str]:
        """Create the Artifactory publishing plugin in buildSrc"""
        try:
            buildsrc_dir = work_dir / 'buildSrc' / 'src' / 'main' / 'groovy'
            buildsrc_dir.mkdir(parents=True, exist_ok=True)
            
            plugin_file = buildsrc_dir / 'ArtifactoryPublishingPlugin.gradle'
            plugin_file.write_text(self.plugin_template)
            
            # Create build.gradle for buildSrc
            buildsrc_build = work_dir / 'buildSrc' / 'build.gradle'
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
            
            return True, "Publishing plugin created successfully"
            
        except Exception as e:
            return False, f"Error creating publishing plugin: {str(e)}"
    
    def remove_nexus_references(self, work_dir: Path) -> Tuple[bool, str, List[str]]:
        """Remove all Nexus publishing references from build files"""
        changes = []
        try:
            # Find all build.gradle and build.gradle.kts files
            build_files = list(work_dir.rglob('build.gradle*'))
            
            for build_file in build_files:
                content = build_file.read_text()
                original_content = content
                
                # Remove Nexus plugin applications
                content = re.sub(r"apply plugin: ['\"]maven-publish['\"]", '', content)
                content = re.sub(r"apply plugin: ['\"]com.jfrog.artifactory['\"]", '', content)
                content = re.sub(r"id ['\"]maven-publish['\"]", '', content)
                content = re.sub(r"id ['\"]com.jfrog.artifactory['\"]", '', content)
                
                # Remove Nexus publishing blocks
                content = re.sub(r'publishing\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', content, flags=re.DOTALL)
                
                # Remove Nexus repository configurations
                content = re.sub(r'maven\s*\{\s*url\s*.*nexus.*\}', '', content, flags=re.DOTALL)
                content = re.sub(r'maven\s*\{\s*url\s*.*sonatype.*\}', '', content, flags=re.DOTALL)
                
                if content != original_content:
                    build_file.write_text(content)
                    changes.append(f"Cleaned Nexus references from {build_file.relative_to(work_dir)}")
            
            return True, "Nexus references removed successfully", changes
            
        except Exception as e:
            return False, f"Error removing Nexus references: {str(e)}", changes
    
    def update_settings_gradle(self, work_dir: Path) -> Tuple[bool, str, List[str]]:
        """Update settings.gradle to use Artifactory for dependency resolution"""
        changes = []
        try:
            settings_files = list(work_dir.rglob('settings.gradle*'))
            
            # Separate configuration for dependency resolution and plugin management
            artifactory_config = f"""
pluginManagement {{
    repositories {{
        maven {{
            url '{self.artifactory_url}/libs-release'
            credentials {{
                username = '{self.artifactory_username}'
                password = '{self.artifactory_password}'
            }}
        }}
        gradlePluginPortal()
    }}
}}

dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        // Use libs-release for dependency resolution (read-only)
        maven {{
            url '{self.artifactory_url}/libs-release'
            credentials {{
                username = '{self.artifactory_username}'
                password = '{self.artifactory_password}'
            }}
        }}
        // Fallback to libs-snapshot for snapshot dependencies
        maven {{
            url '{self.artifactory_url}/libs-snapshot'
            credentials {{
                username = '{self.artifactory_username}'
                password = '{self.artifactory_password}'
            }}
        }}
        mavenCentral()
    }}
}}
"""
            
            for settings_file in settings_files:
                content = settings_file.read_text()
                
                # Add Artifactory configuration at the beginning
                if 'artifactory' not in content.lower():
                    new_content = artifactory_config + '\n' + content
                    settings_file.write_text(new_content)
                    changes.append(f"Updated {settings_file.relative_to(work_dir)} with Artifactory dependency resolution configuration")
            
            return True, "settings.gradle updated successfully", changes
            
        except Exception as e:
            return False, f"Error updating settings.gradle: {str(e)}", changes
    
    def update_build_gradle_files(self, work_dir: Path) -> Tuple[bool, str, List[str]]:
        """Update build.gradle files to apply the Artifactory publishing plugin"""
        changes = []
        try:
            build_files = list(work_dir.rglob('build.gradle*'))
            
            for build_file in build_files:
                content = build_file.read_text()
                
                # Skip buildSrc build.gradle files as they are for the plugin itself
                if 'buildSrc' in str(build_file):
                    continue
                
                # Add plugin application if not present
                if 'ArtifactoryPublishingPlugin' not in content:
                    # Add at the beginning of the file
                    plugin_application = "// Artifactory publishing plugin\napply plugin: ArtifactoryPublishingPlugin\n\n"
                    new_content = plugin_application + content
                    build_file.write_text(new_content)
                    changes.append(f"Added Artifactory publishing plugin to {build_file.relative_to(work_dir)}")
            
            return True, "build.gradle files updated successfully", changes
            
        except Exception as e:
            return False, f"Error updating build.gradle files: {str(e)}", changes