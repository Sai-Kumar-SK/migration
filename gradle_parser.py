import os
import re
import glob
from pathlib import Path
from typing import List, Dict, Optional, Tuple

class GradleProjectParser:
    """Parser for analyzing Gradle project structure and dependencies."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.gradle_files = []
        self.gradle_wrapper_properties = None
        self.is_gradle_platform = False
        self.libs_version_content = ""
        
    def find_all_gradle_files(self) -> List[str]:
        """Find all .gradle files in the project including submodules."""
        gradle_files = []
        
        # Find all .gradle files (Groovy DSL only)
        for file_path in self.project_root.rglob("*.gradle"):
            gradle_files.append(str(file_path))
            
        # Find gradle-wrapper.properties
        wrapper_files = list(self.project_root.rglob("gradle/wrapper/gradle-wrapper.properties"))
        if wrapper_files:
            self.gradle_wrapper_properties = str(wrapper_files[0])
            
        self.gradle_files = gradle_files
        return gradle_files
    
    def detect_gradle_platform(self) -> bool:
        """Detect if project uses Gradle Platform (libs.versions.toml)."""
        libs_toml_path = self.project_root / "gradle" / "libs.versions.toml"
        
        if not libs_toml_path.exists():
            self.is_gradle_platform = False
            return False
            
        try:
            with open(libs_toml_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.libs_version_content = content
                
            # Check for plasmaGradlePlugins under [versions]
            versions_section = re.search(r'\[versions\](.*?)(?=\[|\Z)', content, re.DOTALL)
            if versions_section:
                if 'plasmaGradlePlugins' in versions_section.group(1):
                    self.is_gradle_platform = True
                    return True
                
        except Exception as e:
            print(f"Error reading libs.versions.toml: {e}")
            
        self.is_gradle_platform = False
        return False
    
    def get_project_structure(self) -> Dict:
        """Get complete project structure analysis."""
        return {
            'gradle_files': self.gradle_files,
            'gradle_wrapper_properties': self.gradle_wrapper_properties,
            'is_gradle_platform': self.is_gradle_platform,
            'libs_version_content': self.libs_version_content,
            'root_build_gradle': self._find_root_build_gradle(),
            'settings_gradle': self._find_settings_gradle(),
            'submodule_build_gradles': self._find_submodule_build_gradles()
        }
    
    def _find_root_build_gradle(self) -> Optional[str]:
        """Find root build.gradle file."""
        for filename in ['build.gradle']:
            root_build = self.project_root / filename
            if root_build.exists():
                return str(root_build)
        return None
    
    def _find_settings_gradle(self) -> Optional[str]:
        """Find settings.gradle file."""
        for filename in ['settings.gradle']:
            settings = self.project_root / filename
            if settings.exists():
                return str(settings)
        return None
    
    def _find_submodule_build_gradles(self) -> List[str]:
        """Find build.gradle files in submodules (excluding root)."""
        submodule_builds = []
        root_build = self._find_root_build_gradle()
        
        for gradle_file in self.gradle_files:
            if gradle_file != root_build and 'buildSrc' not in gradle_file:
                # Check if this is a build.gradle (not settings or other gradle files)
                if gradle_file.endswith('build.gradle') or gradle_file.endswith('build.gradle.kts'):
                    submodule_builds.append(gradle_file)
                    
        return submodule_builds
    
    def analyze_build_file(self, file_path: str) -> Dict:
        """Analyze a build.gradle file for specific patterns."""
        analysis = {
            'has_nexus_plugin': False,
            'has_nexus_credentials': False,
            'has_upload_archives': False,
            'has_nexus_block': False,
            'has_wrapper_block': False,
            'has_plugins_block': False,
            'has_artifactory_plugin': False,
            'nexus_references': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for Nexus references
            nexus_patterns = [
                r'classpath\s+["\']com\.bmuschko:gradle-nexus-plugin[^"\']*["\']',
                r'def\s+nexusCredentialsLocation\s*=',
                r'ext\s*\{[^}]*nexus',
                r'uploadArchivesUrl\s*=\s*[^}]*nexus',
                r'nexusCredentials\s*=',
                r'nexusUsername\s*=',
                r'nexusPassword\s*=',
                r'apply\s+plugin\s*:\s*["\']com\.bmuschko\.nexus["\']',
                r'nexus\s*\{',
                r'wrapper\s*\{[^}]*nexus',
                r'uploadArchives\.enabled\s*=',
                r'printin\([^)]*Branch[^)]*uploadArchivesUri[^)]*\)',
                r'if\s*\(\s*ext\.nexusCredentials\.exists\(\)\s*\)'
            ]
            
            for pattern in nexus_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    analysis['nexus_references'].extend(matches)
                    
            # Set specific flags based on patterns found
            analysis['has_nexus_plugin'] = bool(re.search(r'com\.bmuschko.*nexus', content, re.IGNORECASE))
            analysis['has_nexus_credentials'] = bool(re.search(r'nexusCredentialsLocation|nexusCredentials\s*=', content, re.IGNORECASE))
            analysis['has_upload_archives'] = bool(re.search(r'uploadArchives\.(enabled|url)', content, re.IGNORECASE))
            analysis['has_nexus_block'] = bool(re.search(r'nexus\s*\{', content, re.IGNORECASE))
            analysis['has_wrapper_block'] = bool(re.search(r'wrapper\s*\{[^}]*nexus', content, re.IGNORECASE | re.DOTALL))
            analysis['has_plugins_block'] = bool(re.search(r'plugins\s*\{', content, re.IGNORECASE))
            analysis['has_artifactory_plugin'] = bool(re.search(r'com\.jfrog\.artifactory', content, re.IGNORECASE))
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            
        return analysis


def main():
    """Test the parser with a sample project."""
    import sys
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = "."
        
    parser = GradleProjectParser(project_path)
    
    print("Finding Gradle files...")
    gradle_files = parser.find_all_gradle_files()
    print(f"Found {len(gradle_files)} Gradle files")
    
    print("\nDetecting Gradle Platform usage...")
    is_platform = parser.detect_gradle_platform()
    print(f"Using Gradle Platform: {is_platform}")
    
    if is_platform:
        print("Gradle Platform detected - simpler migration steps will be used")
    else:
        print("Standard Gradle project detected - full migration workflow will be applied")
    
    structure = parser.get_project_structure()
    print(f"\nRoot build.gradle: {structure['root_build_gradle']}")
    print(f"Settings.gradle: {structure['settings_gradle']}")
    print(f"Submodule build.gradle files: {len(structure['submodule_build_gradles'])}")
    
    # Analyze root build.gradle
    if structure['root_build_gradle']:
        analysis = parser.analyze_build_file(structure['root_build_gradle'])
        print(f"\nRoot build.gradle analysis:")
        for key, value in analysis.items():
            if key == 'nexus_references':
                print(f"  {key}: {len(value)} references found")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()