import os
import shutil
from pathlib import Path
from typing import Optional, Dict

class HzPublishSetup:
    """Handles setup of hzPublish plugin in buildSrc directory."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.buildsrc_dir = self.project_root / "buildSrc"
        self.groovy_dir = self.buildsrc_dir / "src" / "main" / "groovy"
        self.hzpublish_file = self.groovy_dir / "hzPublish.gradle"
        
    def setup_buildsrc_structure(self) -> bool:
        """Create buildSrc directory structure if it doesn't exist.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create buildSrc directory structure
            self.groovy_dir.mkdir(parents=True, exist_ok=True)
            
            # Create buildSrc build.gradle if it doesn't exist
            buildsrc_build = self.buildsrc_dir / "build.gradle"
            if not buildsrc_build.exists():
                buildsrc_content = """plugins {
    id 'groovy-gradle-plugin'
}

gradlePlugin {
    plugins {
        hzPublish {
            id = 'hzPublish'
            implementationClass = 'HzPublishPlugin'
        }
    }
}
"""
                with open(buildsrc_build, 'w', encoding='utf-8') as f:
                    f.write(buildsrc_content)
                    
            return True
            
        except Exception as e:
            print(f"Error setting up buildSrc structure: {e}")
            return False
    
    def copy_artifactory_plugin(self, source_template_path: str) -> bool:
        """Copy artifactory.gradle to hzPublish.gradle.
        
        Args:
            source_template_path: Path to the artifactory.gradle template
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure buildSrc structure exists
            if not self.setup_buildsrc_structure():
                return False
            
            # Copy the template file
            source_file = Path(source_template_path)
            if not source_file.exists():
                print(f"Source template not found: {source_template_path}")
                return False
            
            shutil.copy2(source_file, self.hzpublish_file)
            print(f"Copied {source_template_path} to {self.hzpublish_file}")
            
            return True
            
        except Exception as e:
            print(f"Error copying plugin file: {e}")
            return False
    
    def create_hzpublish_plugin_class(self) -> bool:
        """Create the HzPublishPlugin class file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            plugin_class_file = self.groovy_dir / "HzPublishPlugin.groovy"
            
            plugin_content = """import org.gradle.api.Plugin
import org.gradle.api.Project

class HzPublishPlugin implements Plugin<Project> {
    void apply(Project project) {
        // Apply the hzPublish.gradle script
        project.apply from: project.rootProject.file('buildSrc/src/main/groovy/hzPublish.gradle')
    }
}
"""
            
            with open(plugin_class_file, 'w', encoding='utf-8') as f:
                f.write(plugin_content)
                
            print(f"Created HzPublishPlugin class at {plugin_class_file}")
            return True
            
        except Exception as e:
            print(f"Error creating plugin class: {e}")
            return False
    
    def setup_complete_hzpublish(self, source_template_path: str) -> Dict:
        """Complete setup of hzPublish plugin.
        
        Args:
            source_template_path: Path to the artifactory-publishing-enhanced.gradle template
            
        Returns:
            Dict with setup results
        """
        result = {
            'buildsrc_structure_created': False,
            'plugin_copied': False,
            'plugin_class_created': False,
            'errors': []
        }
        
        # Setup buildSrc structure
        if self.setup_buildsrc_structure():
            result['buildsrc_structure_created'] = True
        else:
            result['errors'].append("Failed to create buildSrc structure")
            return result
        
        # Copy the enhanced plugin template
        if self.copy_artifactory_plugin(source_template_path):
            result['plugin_copied'] = True
        else:
            result['errors'].append("Failed to copy plugin template")
        
        # Create plugin class
        if self.create_hzpublish_plugin_class():
            result['plugin_class_created'] = True
        else:
            result['errors'].append("Failed to create plugin class")
        
        return result
    
    def verify_hzpublish_setup(self) -> Dict:
        """Verify that hzPublish plugin is properly set up.
        
        Returns:
            Dict with verification results
        """
        result = {
            'buildsrc_exists': False,
            'hzpublish_file_exists': False,
            'plugin_class_exists': False,
            'buildsrc_build_exists': False,
            'all_good': False
        }
        
        try:
            # Check buildSrc directory
            result['buildsrc_exists'] = self.buildsrc_dir.exists()
            
            # Check hzPublish.gradle file
            result['hzpublish_file_exists'] = self.hzpublish_file.exists()
            
            # Check plugin class file
            plugin_class_file = self.groovy_dir / "HzPublishPlugin.groovy"
            result['plugin_class_exists'] = plugin_class_file.exists()
            
            # Check buildSrc build.gradle
            buildsrc_build = self.buildsrc_dir / "build.gradle"
            result['buildsrc_build_exists'] = buildsrc_build.exists()
            
            # Overall status
            result['all_good'] = all([
                result['buildsrc_exists'],
                result['hzpublish_file_exists'],
                result['plugin_class_exists'],
                result['buildsrc_build_exists']
            ])
            
        except Exception as e:
            print(f"Error verifying setup: {e}")
            
        return result


def main():
    """Test the HzPublish setup."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hzpublish_setup.py <project_root> [template_path]")
        return
    
    project_root = sys.argv[1]
    template_path = sys.argv[2] if len(sys.argv) > 2 else "templates/artifactory.gradle"
    
    setup = HzPublishSetup(project_root)
    
    print(f"Setting up hzPublish plugin in {project_root}...")
    
    # Run complete setup
    result = setup.setup_complete_hzpublish(template_path)
    
    print("\nSetup Results:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    # Verify setup
    print("\nVerification:")
    verification = setup.verify_hzpublish_setup()
    for key, value in verification.items():
        print(f"  {key}: {value}")
    
    if verification['all_good']:
        print("\n✅ hzPublish plugin setup completed successfully!")
    else:
        print("\n❌ Some issues found during setup")


if __name__ == "__main__":
    main()