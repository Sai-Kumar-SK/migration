import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class GradlePlatformMigrator:
    """Handles migration for Gradle Platform projects (with libs.versions.toml)"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.libs_versions_toml = self.project_root / "gradle" / "libs.versions.toml"
        self.buildsrc_build_gradle = self.project_root / "buildSrc" / "build.gradle"
        self.buildsrc_settings_gradle = self.project_root / "buildSrc" / "settings.gradle"
        self.root_settings_gradle = self.project_root / "settings.gradle"
        
    def update_libs_versions_toml(self) -> Dict:
        """Update libs.versions.toml file with Artifactory plugins and remove Nexus plugins."""
        result = {
            'success': False,
            'file_path': str(self.libs_versions_toml),
            'artifactory_plugins_added': [],
            'nexus_plugins_removed': [],
            'changes_made': False,
            'errors': []
        }
        
        try:
            if not self.libs_versions_toml.exists():
                result['errors'].append("libs.versions.toml file not found")
                return result
            
            with open(self.libs_versions_toml, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Define required Artifactory plugins
            artifactory_plugins = {
                'plugin-publishing-artifactory': 'ops.plasma.publishing-artifactory:ops.plasma.publishing-artifactory.gradle.plugin',
                'plugin-repositories-artifactory': 'ops.plasma.repositories-artifactory:ops.plasma.repositories-artifactory.gradle.plugin'
            }
            
            # Define Nexus plugins to remove
            nexus_plugins = {
                'plugin-publishing-nexus': 'ops.plasma.publishing-nexus:ops.plasma.publishing-nexus.gradle.plugin',
                'plugin-repositories-nexus': 'ops.plasma.repositories-nexus:ops.plasma.repositories-nexus.gradle.plugin'
            }
            
            # Check if we're in [libraries] section
            libraries_section_match = re.search(r'\[libraries\](.*?)(?=\[|\Z)', content, re.DOTALL)
            if not libraries_section_match:
                result['errors'].append("[libraries] section not found in libs.versions.toml")
                return result
            
            libraries_section = libraries_section_match.group(1)
            
            # Remove Nexus plugins
            for plugin_key, plugin_module in nexus_plugins.items():
                # Pattern to match the plugin declaration
                pattern = rf'{re.escape(plugin_key)}\s*=\s*\{{\s*module\s*=\s*["\']{re.escape(plugin_module)}["\']\s*,\s*versions\.ref\s*=\s*["\']plasmaGradlePlugins["\']\s*\}}'
                
                if re.search(pattern, libraries_section, re.MULTILINE):
                    # Remove the plugin
                    libraries_section = re.sub(pattern + r'\s*\n?', '', libraries_section)
                    result['nexus_plugins_removed'].append(plugin_key)
                    result['changes_made'] = True
            
            # Add Artifactory plugins if not present
            for plugin_key, plugin_module in artifactory_plugins.items():
                # Check if plugin already exists
                pattern = rf'{re.escape(plugin_key)}\s*='
                if not re.search(pattern, libraries_section):
                    # Add the plugin at the end of libraries section
                    new_plugin = f'{plugin_key} = {{ module = "{plugin_module}", versions.ref = "plasmaGradlePlugins" }}'
                    libraries_section = libraries_section.rstrip() + '\n' + new_plugin + '\n'
                    result['artifactory_plugins_added'].append(plugin_key)
                    result['changes_made'] = True
            
            # Update the content
            if result['changes_made']:
                new_content = content[:libraries_section_match.start()] + '[libraries]' + libraries_section
                if libraries_section_match.end() < len(content):
                    new_content += content[libraries_section_match.end():]
                
                # Write back the updated content
                with open(self.libs_versions_toml, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                result['success'] = True
                result['message'] = "libs.versions.toml updated successfully"
            else:
                result['message'] = "No changes needed in libs.versions.toml"
                result['success'] = True
            
        except Exception as e:
            result['errors'].append(f"Error updating libs.versions.toml: {str(e)}")
        
        return result
    
    def update_buildsrc_build_gradle(self) -> Dict:
        """Update buildSrc/build.gradle to replace Nexus plugins with Artifactory plugins."""
        result = {
            'success': False,
            'file_path': str(self.buildsrc_build_gradle),
            'nexus_replaced': [],
            'artifactory_added': [],
            'changes_made': False,
            'errors': []
        }
        
        try:
            if not self.buildsrc_build_gradle.exists():
                result['errors'].append("buildSrc/build.gradle file not found")
                return result
            
            with open(self.buildsrc_build_gradle, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Define plugin replacements
            plugin_replacements = {
                'libs.plugin.publishing-nexus': 'libs.plugin.publishing-artifactory',
                'libs.plugin.repositories-nexus': 'libs.plugin.repositories-artifactory'
            }
            
            # Find dependencies block
            dependencies_match = re.search(r'dependencies\s*\{([^}]*)\}', content, re.DOTALL)
            if not dependencies_match:
                result['errors'].append("dependencies block not found in buildSrc/build.gradle")
                return result
            
            dependencies_block = dependencies_match.group(1)
            
            # Replace Nexus plugins with Artifactory plugins
            for nexus_plugin, artifactory_plugin in plugin_replacements.items():
                if nexus_plugin in dependencies_block:
                    # Replace the plugin
                    dependencies_block = dependencies_block.replace(nexus_plugin, artifactory_plugin)
                    result['nexus_replaced'].append(nexus_plugin)
                    result['artifactory_added'].append(artifactory_plugin)
                    result['changes_made'] = True
            
            # If repositories-nexus was not found but we have publishing-nexus, 
            # we should add repositories-artifactory
            if 'libs.plugin.publishing-nexus' in original_content and 'libs.plugin.repositories-nexus' not in original_content:
                if 'libs.plugin.repositories-artifactory' not in dependencies_block:
                    # Add repositories-artifactory
                    # Find the line with publishing-artifactory and add repositories-artifactory after it
                    lines = dependencies_block.split('\n')
                    new_lines = []
                    for line in lines:
                        new_lines.append(line)
                        if 'libs.plugin.publishing-artifactory' in line and 'implementation' in line:
                            # Add repositories-artifactory after this line
                            new_lines.append(line.replace('publishing-artifactory', 'repositories-artifactory'))
                            result['artifactory_added'].append('libs.plugin.repositories-artifactory')
                            result['changes_made'] = True
                    
                    dependencies_block = '\n'.join(new_lines)
            
            # Update the content
            if result['changes_made']:
                new_content = content[:dependencies_match.start()] + 'dependencies {' + dependencies_block + '}' + content[dependencies_match.end():]
                
                # Write back the updated content
                with open(self.buildsrc_build_gradle, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                result['success'] = True
                result['message'] = "buildSrc/build.gradle updated successfully"
            else:
                result['message'] = "No changes needed in buildSrc/build.gradle"
                result['success'] = True
            
        except Exception as e:
            result['errors'].append(f"Error updating buildSrc/build.gradle: {str(e)}")
        
        return result
    
    def check_buildsrc_settings_gradle(self) -> Dict:
        """Check if buildSrc/settings.gradle exists and report."""
        result = {
            'exists': False,
            'file_path': str(self.buildsrc_settings_gradle),
            'message': ''
        }
        
        try:
            if self.buildsrc_settings_gradle.exists():
                result['exists'] = True
                result['message'] = "buildSrc/settings.gradle found"
                print(f"⚠️  buildSrc/settings.gradle found at: {self.buildsrc_settings_gradle}")
            else:
                result['message'] = "buildSrc/settings.gradle not found"
        
        except Exception as e:
            result['message'] = f"Error checking buildSrc/settings.gradle: {str(e)}"
        
        return result
    
    def validate_root_settings_gradle(self) -> Dict:
        """Validate that root settings.gradle has minimal structure."""
        result = {
            'valid': False,
            'file_path': str(self.root_settings_gradle),
            'content': '',
            'errors': []
        }
        
        try:
            if not self.root_settings_gradle.exists():
                result['errors'].append("root settings.gradle file not found")
                return result
            
            with open(self.root_settings_gradle, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result['content'] = content
            
            # Check for minimal structure - should only contain rootProject.name and includes
            lines = content.strip().split('\n')
            
            # Remove empty lines and comments
            significant_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('//'):
                    significant_lines.append(stripped)
            
            # Check each significant line
            for line in significant_lines:
                if not (line.startswith('rootProject.name') or line.startswith('include')):
                    result['errors'].append(f"Non-minimal content found: {line}")
            
            # Check if rootProject.name exists
            has_rootproject = any(line.startswith('rootProject.name') for line in significant_lines)
            if not has_rootproject:
                result['errors'].append("rootProject.name declaration not found")
            
            if not result['errors']:
                result['valid'] = True
                result['message'] = "Root settings.gradle has minimal structure"
            else:
                result['message'] = "Root settings.gradle has non-minimal content"
                print(f"❌ Root settings.gradle content (non-minimal):")
                print(content)
        
        except Exception as e:
            result['errors'].append(f"Error validating root settings.gradle: {str(e)}")
        
        return result
    
    def run_gradle_platform_migration(self) -> Dict:
        """Run complete Gradle Platform migration."""
        print("\n=== Starting Gradle Platform Migration ===")
        
        results = {
            'libs_versions_updated': None,
            'buildsrc_build_updated': None,
            'buildsrc_settings_checked': None,
            'root_settings_validated': None,
            'success': False,
            'errors': []
        }
        
        # Step 1: Update libs.versions.toml
        print("\n1. Updating libs.versions.toml...")
        results['libs_versions_updated'] = self.update_libs_versions_toml()
        
        # Step 2: Update buildSrc/build.gradle
        print("\n2. Updating buildSrc/build.gradle...")
        results['buildsrc_build_updated'] = self.update_buildsrc_build_gradle()
        
        # Step 3: Check buildSrc/settings.gradle
        print("\n3. Checking buildSrc/settings.gradle...")
        results['buildsrc_settings_checked'] = self.check_buildsrc_settings_gradle()
        
        # Step 4: Validate root settings.gradle
        print("\n4. Validating root settings.gradle...")
        results['root_settings_validated'] = self.validate_root_settings_gradle()
        
        # Check overall success
        all_success = all([
            results['libs_versions_updated'] and results['libs_versions_updated']['success'],
            results['buildsrc_build_updated'] and results['buildsrc_build_updated']['success'],
            results['root_settings_validated'] and results['root_settings_validated']['valid']
        ])
        
        results['success'] = all_success
        
        if all_success:
            print("\n✅ Gradle Platform migration completed successfully!")
        else:
            print("\n❌ Gradle Platform migration completed with issues")
        
        return results


def main():
    """Test the Gradle Platform migrator."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python gradle_platform_migrator.py <project_root>")
        return
    
    project_root = sys.argv[1]
    
    migrator = GradlePlatformMigrator(project_root)
    results = migrator.run_gradle_platform_migration()
    
    print("\nMigration Results:")
    for key, value in results.items():
        if key != 'errors':
            print(f"  {key}: {value}")
    
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")


if __name__ == "__main__":
    main()