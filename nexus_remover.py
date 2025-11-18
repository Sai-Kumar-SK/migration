import re
import os
from typing import List, Dict, Optional, Tuple

class NexusRemover:
    """Handles removal of Nexus references from Gradle build files."""
    
    def __init__(self):
        self.nexus_patterns = [
            # Nexus plugin classpath
            r'classpath\s+["\']com\.bmuschko:gradle-nexus-plugin[^"\']*["\']',
            # Nexus credentials location
            r'def\s+nexusCredentialsLocation\s*=\s*System\.properties\[\'user\.home\'\]\s*\+\s*"/\.secure/nexus\.credentials"',
            # Ext block with Nexus configuration
            r'ext\s*\{[^}]*?(?:branchName|repoName|uploadArchivesUrl|nexusCredentials|nexusUsername|nexusPassword)\s*=\s*[^}]*?\}',
            # Print statement with branch info
            r'printin\([^)]*Branch[^)]*uploadArchivesUri[^)]*\)',
            # Credentials apply block
            r'if\s*\(\s*ext\.nexusCredentials\.exists\(\)\s*\)\s*\{[^}]*apply\s+from\s*:\s*ext\.nexusCredentials[^}]*\}',
            # Upload archives enabled
            r'uploadArchives\.enabled\s*=\s*(?:true|false)',
            # Nexus plugin application
            r'apply\s+plugin\s*:\s*["\']com\.bmuschko\.nexus["\']',
            # Nexus configuration block
            r'nexus\s*\{[^}]*?(?:sign|repositoryUrl)[^}]*?\}',
            # Wrapper block with Nexus
            r'wrapper\s*\{[^}]*?(?:gradleVersion|distributionUrl)[^}]*?\}'
        ]
        
    def remove_nexus_from_build_gradle(self, file_path: str) -> Tuple[bool, List[str]]:
        """Remove all Nexus references from a build.gradle file.
        
        Args:
            file_path: Path to build.gradle file
            
        Returns:
            Tuple of (success: bool, removed_items: List[str])
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            removed_items = []
            
            # Remove each Nexus pattern
            for pattern in self.nexus_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    removed_items.extend(matches)
                    content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
                    
            # Clean up empty lines and whitespace
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                # Skip empty lines that were created by removals
                if line.strip() == '' and len(cleaned_lines) > 0 and cleaned_lines[-1].strip() == '':
                    continue
                cleaned_lines.append(line)
            
            # Remove trailing empty lines
            while cleaned_lines and cleaned_lines[-1].strip() == '':
                cleaned_lines.pop()
                
            content = '\n'.join(cleaned_lines)
            
            # Write back if changes were made
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                print(f"Removed {len(removed_items)} Nexus references from {file_path}")
                return True, removed_items
            else:
                print(f"No Nexus references found in {file_path}")
                return False, []
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return False, []
    
    def add_artifactory_plugin(self, file_path: str, artifactory_version: str = "4.28.2") -> bool:
        """Add jfrog.artifactory plugin to build.gradle file.
        
        Args:
            file_path: Path to build.gradle file
            artifactory_version: Version of artifactory plugin
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if artifactory plugin already exists
            if 'com.jfrog.artifactory' in content:
                print(f"Artifactory plugin already exists in {file_path}")
                return False
            
            # Check if plugins block exists
            plugins_match = re.search(r'plugins\s*\{[^}]*\}', content, re.DOTALL)
            
            if plugins_match:
                # Add artifactory plugin to existing plugins block
                plugins_block = plugins_match.group(0)
                
                # Check if it's Kotlin DSL
                if file_path.endswith('.kts'):
                    new_plugin = f'    id("com.jfrog.artifactory") version "{artifactory_version}"'
                else:
                    new_plugin = f"    id 'com.jfrog.artifactory' version '{artifactory_version}'"
                
                # Insert before the closing brace
                if plugins_block.rstrip().endswith('}'):
                    new_plugins_block = plugins_block.rstrip()[:-1] + '\n' + new_plugin + '\n}'
                    content = content.replace(plugins_block, new_plugins_block)
                else:
                    # Fallback: append to end of file
                    if file_path.endswith('.kts'):
                        content += f'\n\nplugins {{\n    id("com.jfrog.artifactory") version "{artifactory_version}"\n}}'
                    else:
                        content += f"\n\nplugins {{\n    id 'com.jfrog.artifactory' version '{artifactory_version}'\n}}"
            else:
                # Create new plugins block at the end of file
                if file_path.endswith('.kts'):
                    content += f'\n\nplugins {{\n    id("com.jfrog.artifactory") version "{artifactory_version}"\n}}'
                else:
                    content += f"\n\nplugins {{\n    id 'com.jfrog.artifactory' version '{artifactory_version}'\n}}"
            
            # Write updated content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"Added Artifactory plugin to {file_path}")
            return True
            
        except Exception as e:
            print(f"Error adding Artifactory plugin to {file_path}: {e}")
            return False
    
    def process_root_build_gradle(self, file_path: str, artifactory_version: str = "4.28.2") -> Dict:
        """Process root build.gradle file: remove Nexus and add Artifactory.
        
        Args:
            file_path: Path to root build.gradle file
            artifactory_version: Version of artifactory plugin
            
        Returns:
            Dict with processing results
        """
        result = {
            'file_path': file_path,
            'nexus_removed': False,
            'removed_items': [],
            'artifactory_added': False,
            'errors': []
        }
        
        # Remove Nexus references
        nexus_success, removed_items = self.remove_nexus_from_build_gradle(file_path)
        result['nexus_removed'] = nexus_success
        result['removed_items'] = removed_items
        
        # Add Artifactory plugin
        artifactory_success = self.add_artifactory_plugin(file_path, artifactory_version)
        result['artifactory_added'] = artifactory_success
        
        if not nexus_success and not artifactory_success:
            result['errors'].append("No changes made to file")
        
        return result
    
    def apply_hzpublish_to_submodule(self, file_path: str) -> bool:
        """Apply hzPublish plugin to submodule build.gradle file.
        
        Args:
            file_path: Path to submodule build.gradle file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove uploadArchives.enabled = true if it exists
            content = re.sub(r'uploadArchives\.enabled\s*=\s*true\s*\n?', '', content)
            
            # Check if hzPublish plugin already exists
            if "id 'hzPublish'" in content or 'id("hzPublish")' in content:
                print(f"hzPublish plugin already exists in {file_path}")
                # Still write the cleaned content
                if content != open(file_path, 'r', encoding='utf-8').read():
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Cleaned uploadArchives from {file_path}")
                return True
            
            # Check if plugins block exists
            plugins_match = re.search(r'plugins\s*\{[^}]*\}', content, re.DOTALL)
            
            if plugins_match:
                # Add hzPublish plugin to existing plugins block
                plugins_block = plugins_match.group(0)
                
                # Check if it's Kotlin DSL
                if file_path.endswith('.kts'):
                    new_plugin = '    id("hzPublish")'
                else:
                    new_plugin = "    id 'hzPublish'"
                
                # Insert before the closing brace
                if plugins_block.rstrip().endswith('}'):
                    new_plugins_block = plugins_block.rstrip()[:-1] + '\n' + new_plugin + '\n}'
                    content = content.replace(plugins_block, new_plugins_block)
                else:
                    # Fallback: create new plugins block at beginning
                    if file_path.endswith('.kts'):
                        content = f'plugins {{\n    id("hzPublish")\n}}\n\n' + content
                    else:
                        content = f"plugins {{\n    id 'hzPublish'\n}}\n\n" + content
            else:
                # Create new plugins block at the beginning of file
                if file_path.endswith('.kts'):
                    content = f'plugins {{\n    id("hzPublish")\n}}\n\n' + content
                else:
                    content = f"plugins {{\n    id 'hzPublish'\n}}\n\n" + content
            
            # Write updated content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"Applied hzPublish plugin to {file_path}")
            return True
            
        except Exception as e:
            print(f"Error applying hzPublish plugin to {file_path}: {e}")
            return False


def main():
    """Test the Nexus remover."""
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        print("Please provide a build.gradle file to test")
        return
    
    remover = NexusRemover()
    
    # Test analysis
    from gradle_parser import GradleProjectParser
    parser = GradleProjectParser(os.path.dirname(test_file))
    analysis = parser.analyze_build_file(test_file)
    
    print(f"Analysis of {test_file}:")
    for key, value in analysis.items():
        if key == 'nexus_references':
            print(f"  {key}: {len(value)} references")
            for ref in value[:3]:  # Show first 3
                print(f"    - {ref}")
            if len(value) > 3:
                print(f"    ... and {len(value) - 3} more")
        else:
            print(f"  {key}: {value}")
    
    # Test removal
    print(f"\nProcessing {test_file}...")
    result = remover.process_root_build_gradle(test_file)
    
    print(f"Processing results:")
    print(f"  Nexus removed: {result['nexus_removed']}")
    print(f"  Items removed: {len(result['removed_items'])}")
    print(f"  Artifactory added: {result['artifactory_added']}")
    if result['errors']:
        print(f"  Errors: {result['errors']}")


if __name__ == "__main__":
    main()