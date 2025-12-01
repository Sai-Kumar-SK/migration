import re
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from wrapper_updater import update_gradle_wrapper
from settings_template import get_version_catalog_settings_template

class GradlePlatformMigrator:
    """Handles migration for Gradle Platform projects (with libs.versions.toml)"""
    
    def __init__(self, project_root: str, verbose: bool = False):
        self.project_root = Path(project_root)
        self.verbose = verbose
        self.log = logging.getLogger("horizon")
        self.libs_versions_toml = self.project_root / "gradle" / "libs.versions.toml"
        self.buildsrc_build_gradle = self.project_root / "buildSrc" / "build.gradle"
        self.buildsrc_settings_gradle = self.project_root / "buildSrc" / "settings.gradle"
        self.root_settings_gradle = self.project_root / "settings.gradle"
        
    def update_libs_versions_toml(self) -> Dict:
        """Replace repositories-nexus plugin with repositories-artifactory if present."""
        result = {
            'success': False,
            'file_path': str(self.libs_versions_toml),
            'replaced': False,
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
            
            # Check [libraries] section
            libraries_section_match = re.search(r'\[libraries\](.*?)(?=\[|\Z)', content, re.DOTALL)
            if not libraries_section_match:
                result['errors'].append("[libraries] section not found in libs.versions.toml")
                return result
            
            libraries_section = libraries_section_match.group(1)
            # Replace repositories-nexus entry only if present
            nexus_key = 'plugin-repositories-nexus'
            art_key = 'plugin-repositories-artifactory'
            nexus_module = 'ops.plasma.repositories-nexus:ops.plasma.repositories-nexus.gradle.plugin'
            art_module = 'ops.plasma.repositories-artifactory:ops.plasma.repositories-artifactory.gradle.plugin'
            pattern = rf'{re.escape(nexus_key)}\s*=\s*\{{\s*module\s*=\s*["\']{re.escape(nexus_module)}["\']\s*,\s*version\.ref\s*=\s*["\']plasmaGradlePlugins["\']\s*\}}'
            pattern_alt = rf'{re.escape(nexus_key)}\s*=\s*\{{\s*module\s*=\s*["\']{re.escape(nexus_module)}["\']\s*,\s*versions\.ref\s*=\s*["\']plasmaGradlePlugins["\']\s*\}}'
            if re.search(pattern, libraries_section) or re.search(pattern_alt, libraries_section):
                libraries_section = re.sub(pattern, f'{art_key} = {{ module = "{art_module}", version.ref = "plasmaGradlePlugins" }}', libraries_section)
                libraries_section = re.sub(pattern_alt, f'{art_key} = {{ module = "{art_module}", versions.ref = "plasmaGradlePlugins" }}', libraries_section)
                result['replaced'] = True
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
        """Replace implementation libs.plugin.repositories.nexus with .artifactory if found."""
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
            
            # Find dependencies block
            dependencies_match = re.search(r'dependencies\s*\{([^}]*)\}', content, re.DOTALL)
            if not dependencies_match:
                result['errors'].append("dependencies block not found in buildSrc/build.gradle")
                return result
            
            dependencies_block = dependencies_match.group(1)
            # Replace repositories nexus forms
            pat_forms = [
                ('libs.plugin.repositories-nexus', 'libs.plugin.repositories-artifactory'),
                ('libs.plugin.repositories.nexus', 'libs.plugin.repositories.artifactory')
            ]
            for old, new in pat_forms:
                if old in dependencies_block:
                    dependencies_block = dependencies_block.replace(old, new)
                    result['nexus_replaced'].append(old)
                    result['artifactory_added'].append(new)
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
                result['message'] = "repositories-nexus implementation not found; skipped"
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
                if self.verbose:
                    self.log.debug(f"buildSrc/settings.gradle found at: {self.buildsrc_settings_gradle}")
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
                if self.verbose:
                    self.log.debug("Root settings.gradle content (non-minimal)")
                    self.log.debug(content)
        
        except Exception as e:
            result['errors'].append(f"Error validating root settings.gradle: {str(e)}")
        
        return result
    
    def run_gradle_platform_migration(self) -> Dict:
        """Run complete Gradle Platform migration."""
        if self.verbose:
            self.log.info("Starting Gradle Platform Migration")
        
        results = {
            'libs_versions_updated': None,
            'buildsrc_build_updated': None,
            'wrapper_updated': None,
            'buildsrc_settings_checked': None,
            'root_settings_validated': None,
            'buildsrc_libs_updated': None,
            'buildsrc_settings_replaced': None,
            'success': False,
            'errors': []
        }
        
        # Step 1: Update wrapper
        if self.verbose:
            self.log.info("1. Updating gradle-wrapper.properties...")
        wrapper_path = str(self.project_root / 'gradle' / 'wrapper' / 'gradle-wrapper.properties')
        wr = update_gradle_wrapper(wrapper_path)
        results['wrapper_updated'] = wr
        
        # Step 2: Update libs.versions.toml
        if self.verbose:
            self.log.info("1. Updating libs.versions.toml...")
        results['libs_versions_updated'] = self.update_libs_versions_toml()
        
        # Step 3: Update buildSrc/build.gradle
        if self.verbose:
            self.log.info("2. Updating buildSrc/build.gradle...")
        results['buildsrc_build_updated'] = self.update_buildsrc_build_gradle()
        
        # Step 4: Update buildSrc lib groovy plugin ids
        if self.verbose:
            self.log.info("3. Updating buildSrc lib groovy plugin ids...")
        results['buildsrc_libs_updated'] = self.update_lib_groovy_plugin_ids()
        
        # Step 5: Replace buildSrc/settings.gradle with provided template
        if self.verbose:
            self.log.info("4. Replacing buildSrc/settings.gradle with template...")
        results['buildsrc_settings_replaced'] = self.replace_buildsrc_settings_with_template()
        
        # Step 6: Check buildSrc/settings.gradle presence
        if self.verbose:
            self.log.info("5. Checking buildSrc/settings.gradle...")
        results['buildsrc_settings_checked'] = self.check_buildsrc_settings_gradle()
        
        # Step 7: Validate and clean root settings.gradle
        if self.verbose:
            self.log.info("6. Validating root settings.gradle...")
        results['root_settings_validated'] = self.clean_root_settings_gradle()
        
        # Check overall success
        all_success = all([
            results['libs_versions_updated'] and results['libs_versions_updated']['success'],
            results['buildsrc_build_updated'] and results['buildsrc_build_updated']['success'],
            results['wrapper_updated'] and results['wrapper_updated']['success'],
            results['root_settings_validated'] and results['root_settings_validated']['valid']
        ])
        
        results['success'] = all_success
        
        if self.verbose:
            if all_success:
                self.log.info("Gradle Platform migration completed successfully")
            else:
                self.log.info("Gradle Platform migration completed with issues")
        
        return results

    def update_lib_groovy_plugin_ids(self) -> Dict:
        result = {'success': True, 'files_updated': [], 'skipped': []}
        try:
            groovy_dir = self.project_root / 'buildSrc' / 'src' / 'main' / 'groovy'
            if not groovy_dir.exists():
                return result
            for f in groovy_dir.glob('*.lib.groovy'):
                content = f.read_text(encoding='utf-8')
                if "id 'ops.plasma.repositories-nexus'" in content:
                    new_content = content.replace("id 'ops.plasma.repositories-nexus'", "id 'ops.plasma.repositories-artifactory'")
                    f.write_text(new_content, encoding='utf-8')
                    result['files_updated'].append(str(f))
                else:
                    result['skipped'].append(str(f))
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def replace_buildsrc_settings_with_template(self) -> Dict:
        result = {'success': False, 'replaced': False, 'errors': []}
        try:
            tpl = get_version_catalog_settings_template()
            target = self.project_root / 'buildSrc' / 'settings.gradle'
            if tpl and tpl.strip():
                target.write_text(tpl, encoding='utf-8')
                result['success'] = True
                result['replaced'] = True
            else:
                result['errors'].append('VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE not provided')
            return result
        except Exception as e:
            result['errors'].append(str(e))
            return result

    def clean_root_settings_gradle(self) -> Dict:
        result = {'valid': False, 'file_path': str(self.root_settings_gradle), 'errors': []}
        try:
            if not self.root_settings_gradle.exists():
                result['errors'].append('root settings.gradle not found')
                return result
            content = self.root_settings_gradle.read_text(encoding='utf-8')
            content = self._remove_block(content, 'pluginManagement')
            content = self._remove_block(content, 'dependencyResolutionManagement')
            content = self._remove_allprojects(content)
            self.root_settings_gradle.write_text(content, encoding='utf-8')
            # Validate minimal
            lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
            valid = all(not (l.startswith('pluginManagement') or l.startswith('dependencyResolutionManagement') or 'allprojects' in l) for l in lines)
            result['valid'] = valid
            return result
        except Exception as e:
            result['errors'].append(str(e))
            return result

    def _remove_block(self, content: str, block_name: str) -> str:
        m = re.search(rf'{block_name}\s*\{{', content)
        if not m:
            return content
        start = m.start()
        brace = content.find('{', start)
        depth = 0
        end_idx = None
        for i in range(brace, len(content)):
            ch = content[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx is not None:
            return content[:start] + content[end_idx+1:]
        return content

    def _remove_allprojects(self, content: str) -> str:
        m = re.search(r'(?:gradle\.)?allprojects\s*\{', content, re.IGNORECASE)
        if not m:
            return content
        start = m.start()
        brace = content.find('{', start)
        depth = 0
        end_idx = None
        for i in range(brace, len(content)):
            ch = content[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx is not None:
            return content[:start] + content[end_idx+1:]
        return content


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