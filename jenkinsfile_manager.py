import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional

class JenkinsfileManager:
    """Handles Jenkinsfile operations for migration."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.jenkinsfile = self.project_root / "Jenkinsfile"
        
    def replace_jenkinsfile(self, template_path: str) -> Dict:
        """Replace existing Jenkinsfile with template."""
        result = {
            'success': False,
            'old_jenkinsfile_backed_up': False,
            'new_jenkinsfile_copied': False,
            'backup_path': None,
            'errors': []
        }
        
        try:
            template_file = Path(template_path)
            if not template_file.exists():
                result['errors'].append(f"Template file not found: {template_path}")
                return result
            
            # Backup existing Jenkinsfile if it exists
            if self.jenkinsfile.exists():
                backup_path = self.jenkinsfile.with_suffix('.jenkinsfile.backup')
                shutil.copy2(self.jenkinsfile, backup_path)
                result['old_jenkinsfile_backed_up'] = True
                result['backup_path'] = str(backup_path)
                print(f"Backed up existing Jenkinsfile to {backup_path}")
            
            # Copy new Jenkinsfile
            shutil.copy2(template_file, self.jenkinsfile)
            result['new_jenkinsfile_copied'] = True
            result['success'] = True
            
            print(f"Successfully replaced Jenkinsfile with template from {template_path}")
            
        except Exception as e:
            result['errors'].append(f"Error replacing Jenkinsfile: {str(e)}")
        
        return result
    
    def cleanup_jenkinsfile_groovy_files(self) -> Dict:
        """Delete all Jenkinsfile.*.groovy files."""
        result = {
            'success': False,
            'files_found': [],
            'files_deleted': [],
            'errors': []
        }
        
        try:
            # Find all Jenkinsfile.*.groovy files
            pattern = "Jenkinsfile.*.groovy"
            groovy_files = list(self.project_root.glob(pattern))
            
            result['files_found'] = [str(f) for f in groovy_files]
            
            if not groovy_files:
                result['success'] = True
                result['message'] = "No Jenkinsfile.*.groovy files found"
                return result
            
            # Delete each file
            for file_path in groovy_files:
                try:
                    file_path.unlink()
                    result['files_deleted'].append(str(file_path))
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    result['errors'].append(f"Failed to delete {file_path}: {str(e)}")
            
            result['success'] = len(result['errors']) == 0
            
            if result['success']:
                print(f"Successfully deleted {len(result['files_deleted'])} Jenkinsfile.*.groovy files")
            else:
                print(f"Deleted {len(result['files_deleted'])} files with {len(result['errors'])} errors")
            
        except Exception as e:
            result['errors'].append(f"Error during cleanup: {str(e)}")
        
        return result
    
    def get_jenkinsfile_status(self) -> Dict:
        """Get current status of Jenkinsfile and related files."""
        result = {
            'jenkinsfile_exists': False,
            'jenkinsfile_path': str(self.jenkinsfile),
            'jenkinsfile_groovy_files': [],
            'groovy_files_count': 0
        }
        
        try:
            # Check main Jenkinsfile
            result['jenkinsfile_exists'] = self.jenkinsfile.exists()
            
            # Find Jenkinsfile.*.groovy files
            pattern = "Jenkinsfile.*.groovy"
            groovy_files = list(self.project_root.glob(pattern))
            
            result['jenkinsfile_groovy_files'] = [str(f) for f in groovy_files]
            result['groovy_files_count'] = len(groovy_files)
            
        except Exception as e:
            result['error'] = f"Error checking Jenkinsfile status: {str(e)}"
        
        return result


class CompleteMigrationManager:
    """Manages the complete migration process for both Gradle Platform and Standard projects."""
    
    def __init__(self, project_root: str, jenkinsfile_template_path: str):
        self.project_root = Path(project_root)
        self.jenkinsfile_manager = JenkinsfileManager(project_root)
        self.jenkinsfile_template_path = jenkinsfile_template_path
        
    def complete_standard_gradle_migration(self) -> Dict:
        """Complete migration for standard Gradle projects (non-Gradle Platform)."""
        from gradle_migration_workflow import GradleMigrationWorkflow
        
        result = {
            'success': False,
            'gradle_migration': None,
            'jenkinsfile_replacement': None,
            'jenkinsfile_cleanup': None,
            'errors': []
        }
        
        try:
            print("\n=== Completing Standard Gradle Migration ===")
            
            # Step 1: Run the Gradle migration workflow
            print("\n1. Running Gradle migration workflow...")
            workflow = GradleMigrationWorkflow(str(self.project_root))
            gradle_result = workflow.run_migration_workflow("templates/artifactory-publishing-enhanced.gradle")
            result['gradle_migration'] = gradle_result
            
            if not gradle_result.get('success', False):
                result['errors'].append("Gradle migration workflow failed")
                return result
            
            # Step 2: Replace Jenkinsfile
            print("\n2. Replacing Jenkinsfile...")
            jenkinsfile_result = self.jenkinsfile_manager.replace_jenkinsfile(self.jenkinsfile_template_path)
            result['jenkinsfile_replacement'] = jenkinsfile_result
            
            if not jenkinsfile_result['success']:
                result['errors'].append("Jenkinsfile replacement failed")
            
            # Step 3: Cleanup Jenkinsfile.*.groovy files
            print("\n3. Cleaning up Jenkinsfile.*.groovy files...")
            cleanup_result = self.jenkinsfile_manager.cleanup_jenkinsfile_groovy_files()
            result['jenkinsfile_cleanup'] = cleanup_result
            
            if not cleanup_result['success']:
                result['errors'].append("Jenkinsfile cleanup failed")
            
            # Overall success
            result['success'] = len(result['errors']) == 0
            
            if result['success']:
                print("\n✅ Standard Gradle migration completed successfully!")
            else:
                print(f"\n❌ Standard Gradle migration completed with {len(result['errors'])} errors")
            
        except Exception as e:
            result['errors'].append(f"Error in standard Gradle migration: {str(e)}")
        
        return result
    
    def complete_gradle_platform_migration(self) -> Dict:
        """Complete migration for Gradle Platform projects."""
        from gradle_platform_migrator import GradlePlatformMigrator
        
        result = {
            'success': False,
            'gradle_platform_migration': None,
            'jenkinsfile_replacement': None,
            'jenkinsfile_cleanup': None,
            'errors': []
        }
        
        try:
            print("\n=== Completing Gradle Platform Migration ===")
            
            # Step 1: Run the Gradle Platform migration
            print("\n1. Running Gradle Platform migration...")
            platform_migrator = GradlePlatformMigrator(str(self.project_root))
            platform_result = platform_migrator.run_gradle_platform_migration()
            result['gradle_platform_migration'] = platform_result
            
            if not platform_result.get('success', False):
                result['errors'].append("Gradle Platform migration failed")
                return result
            
            # Step 2: Replace Jenkinsfile
            print("\n2. Replacing Jenkinsfile...")
            jenkinsfile_result = self.jenkinsfile_manager.replace_jenkinsfile(self.jenkinsfile_template_path)
            result['jenkinsfile_replacement'] = jenkinsfile_result
            
            if not jenkinsfile_result['success']:
                result['errors'].append("Jenkinsfile replacement failed")
            
            # Step 3: Cleanup Jenkinsfile.*.groovy files
            print("\n3. Cleaning up Jenkinsfile.*.groovy files...")
            cleanup_result = self.jenkinsfile_manager.cleanup_jenkinsfile_groovy_files()
            result['jenkinsfile_cleanup'] = cleanup_result
            
            if not cleanup_result['success']:
                result['errors'].append("Jenkinsfile cleanup failed")
            
            # Overall success
            result['success'] = len(result['errors']) == 0
            
            if result['success']:
                print("\n✅ Gradle Platform migration completed successfully!")
            else:
                print(f"\n❌ Gradle Platform migration completed with {len(result['errors'])} errors")
            
        except Exception as e:
            result['errors'].append(f"Error in Gradle Platform migration: {str(e)}")
        
        return result


def main():
    """Test the Jenkinsfile manager."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python jenkinsfile_manager.py <project_root> <jenkinsfile_template_path>")
        return
    
    project_root = sys.argv[1]
    jenkinsfile_template = sys.argv[2]
    
    # Test Jenkinsfile manager
    manager = JenkinsfileManager(project_root)
    
    print("Jenkinsfile Status:")
    status = manager.get_jenkinsfile_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print(f"\nReplacing Jenkinsfile with template: {jenkinsfile_template}")
    replace_result = manager.replace_jenkinsfile(jenkinsfile_template)
    print("Replace Result:")
    for key, value in replace_result.items():
        print(f"  {key}: {value}")
    
    print("\nCleaning up Jenkinsfile.*.groovy files...")
    cleanup_result = manager.cleanup_jenkinsfile_groovy_files()
    print("Cleanup Result:")
    for key, value in cleanup_result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()