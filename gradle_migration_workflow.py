import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from gradle_parser import GradleProjectParser
from settings_template import append_repositories_to_settings
from nexus_remover import NexusRemover
from hzpublish_setup import HzPublishSetup
from gradle_platform_migrator import GradlePlatformMigrator
from jenkinsfile_manager import CompleteMigrationManager

class GradleMigrationWorkflow:
    """Complete workflow for migrating Gradle projects from Nexus to Artifactory."""
    
    def __init__(self, project_root: str, artifactory_url: str = "https://artifactory.org.com"):
        self.project_root = Path(project_root)
        self.artifactory_url = artifactory_url
        self.parser = GradleProjectParser(project_root)
        self.nexus_remover = NexusRemover()
        self.hzpublish_setup = HzPublishSetup(project_root)
        
    def run_migration_workflow(self, enhanced_plugin_path: str) -> Dict:
        """Run the complete migration workflow.
        
        Args:
            enhanced_plugin_path: Path to artifactory-publishing-enhanced.gradle template
            
        Returns:
            Dict with complete migration results
        """
        print(f"Starting migration workflow for {self.project_root}")
        
        # Step 1: Parse project structure
        print("\n=== Step 1: Analyzing project structure ===")
        structure = self._analyze_project_structure()
        if not structure['success']:
            return structure
        
        # Check if Gradle Platform is used
        if structure['is_gradle_platform']:
            print("\n⚠️  Gradle Platform detected - running simplified migration")
            return self._run_gradle_platform_migration(enhanced_plugin_path)
        
        print("\n🔧 Standard Gradle project detected - proceeding with full migration")
        
        # Step 2: Update settings.gradle
        print("\n=== Step 2: Updating settings.gradle ===")
        settings_result = self._update_settings_gradle()
        
        # Step 3: Process root build.gradle
        print("\n=== Step 3: Processing root build.gradle ===")
        root_build_result = self._process_root_build_gradle()
        
        # Step 4: Setup hzPublish plugin
        print("\n=== Step 4: Setting up hzPublish plugin ===")
        hzpublish_result = self._setup_hzpublish_plugin(enhanced_plugin_path)
        
        # Step 5: Process submodule build.gradle files
        print("\n=== Step 5: Processing submodule build.gradle files ===")
        submodule_results = self._process_submodule_build_gradles()
        
        # Step 6: Complete migration with Jenkinsfile operations
        print("\n=== Step 6: Completing migration with Jenkinsfile operations ===")
        completion_results = self._complete_migration(enhanced_plugin_path)
        
        # Compile results
        results = {
            'success': True,
            'project_structure': structure,
            'settings_gradle': settings_result,
            'root_build_gradle': root_build_result,
            'hzpublish_setup': hzpublish_result,
            'submodule_build_gradles': submodule_results,
            'completion': completion_results,
            'summary': self._generate_summary(
                structure, settings_result, root_build_result, 
                hzpublish_result, submodule_results, completion_results
            )
        }
        
        return results
    
    def _complete_migration(self, enhanced_plugin_path: str) -> Dict:
        """Complete migration with Jenkinsfile operations for standard Gradle projects."""
        try:
            migration_manager = CompleteMigrationManager(str(self.project_root), enhanced_plugin_path)
            complete_results = migration_manager.complete_standard_gradle_migration()
            
            return {
                'success': complete_results['success'],
                'jenkinsfile_replacement': complete_results.get('jenkinsfile_replacement'),
                'jenkinsfile_cleanup': complete_results.get('jenkinsfile_cleanup'),
                'errors': complete_results.get('errors', [])
            }
            
        except Exception as e:
            return {
                'success': False,
                'errors': [f'Completion error: {str(e)}']
            }
    
    def _run_gradle_platform_migration(self, enhanced_plugin_path: str) -> Dict:
        """Run Gradle Platform specific migration."""
        try:
            # Use the Gradle Platform migrator
            platform_migrator = GradlePlatformMigrator(str(self.project_root))
            platform_results = platform_migrator.run_gradle_platform_migration()
            
            if not platform_results.get('success', False):
                return {
                    'success': False,
                    'message': 'Gradle Platform migration failed',
                    'platform_results': platform_results
                }
            
            # Complete the migration with Jenkinsfile operations
            migration_manager = CompleteMigrationManager(str(self.project_root), enhanced_plugin_path)
            complete_results = migration_manager.complete_gradle_platform_migration()
            
            return {
                'success': complete_results['success'],
                'message': 'Gradle Platform migration completed',
                'platform_results': platform_results,
                'complete_results': complete_results,
                'is_gradle_platform': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Gradle Platform migration error: {str(e)}',
                'is_gradle_platform': True
            }
    
    def _analyze_project_structure(self) -> Dict:
        """Analyze project structure and detect Gradle Platform usage."""
        try:
            # Find all Gradle files
            gradle_files = self.parser.find_all_gradle_files()
            print(f"Found {len(gradle_files)} Gradle files")
            
            # Detect Gradle Platform
            is_gradle_platform = self.parser.detect_gradle_platform()
            print(f"Gradle Platform usage: {is_gradle_platform}")
            
            # Get complete structure
            structure = self.parser.get_project_structure()
            
            # Analyze root build.gradle
            root_analysis = {}
            if structure['root_build_gradle']:
                root_analysis = self.parser.analyze_build_file(structure['root_build_gradle'])
                print(f"Root build.gradle analysis: {len(root_analysis['nexus_references'])} Nexus references found")
            
            return {
                'success': True,
                'gradle_files': gradle_files,
                'is_gradle_platform': is_gradle_platform,
                'root_build_gradle': structure['root_build_gradle'],
                'settings_gradle': structure['settings_gradle'],
                'submodule_build_gradles': structure['submodule_build_gradles'],
                'root_analysis': root_analysis
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to analyze project structure: {e}"
            }
    
    def _update_settings_gradle(self) -> Dict:
        """Update settings.gradle with Artifactory repositories."""
        try:
            structure = self.parser.get_project_structure()
            settings_file = structure['settings_gradle']
            
            if not settings_file:
                return {
                    'success': False,
                    'error': 'No settings.gradle file found'
                }
            
            success = append_repositories_to_settings(settings_file, self.artifactory_url)
            
            return {
                'success': success,
                'file_path': settings_file,
                'message': 'Settings.gradle updated successfully' if success else 'Settings.gradle update failed'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to update settings.gradle: {e}"
            }
    
    def _process_root_build_gradle(self) -> Dict:
        """Process root build.gradle file."""
        try:
            structure = self.parser.get_project_structure()
            root_build_file = structure['root_build_gradle']
            
            if not root_build_file:
                return {
                    'success': False,
                    'error': 'No root build.gradle file found'
                }
            
            # Process the file
            result = self.nexus_remover.process_root_build_gradle(root_build_file)
            
            return {
                'success': True,
                'file_path': root_build_file,
                'nexus_removed': result['nexus_removed'],
                'removed_items_count': len(result['removed_items']),
                'artifactory_added': result['artifactory_added'],
                'errors': result['errors']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to process root build.gradle: {e}"
            }
    
    def _setup_hzpublish_plugin(self, enhanced_plugin_path: str) -> Dict:
        """Setup hzPublish plugin in buildSrc directory."""
        try:
            # Run complete setup
            setup_result = self.hzpublish_setup.setup_complete_hzpublish(enhanced_plugin_path)
            
            # Verify setup
            verification = self.hzpublish_setup.verify_hzpublish_setup()
            
            return {
                'success': verification['all_good'],
                'setup_results': setup_result,
                'verification': verification
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to setup hzPublish plugin: {e}"
            }
    
    def _process_submodule_build_gradles(self) -> Dict:
        """Process all submodule build.gradle files."""
        try:
            structure = self.parser.get_project_structure()
            submodule_files = structure['submodule_build_gradles']
            
            results = {
                'total_files': len(submodule_files),
                'processed_files': 0,
                'failed_files': 0,
                'file_results': []
            }
            
            for submodule_file in submodule_files:
                try:
                    success = self.nexus_remover.apply_hzpublish_to_submodule(submodule_file)
                    
                    results['file_results'].append({
                        'file_path': submodule_file,
                        'success': success
                    })
                    
                    if success:
                        results['processed_files'] += 1
                    else:
                        results['failed_files'] += 1
                        
                except Exception as e:
                    results['file_results'].append({
                        'file_path': submodule_file,
                        'success': False,
                        'error': str(e)
                    })
                    results['failed_files'] += 1
            
            return results
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to process submodule build.gradle files: {e}"
            }
    
    def _generate_summary(self, structure: Dict, settings_result: Dict, 
                         root_build_result: Dict, hzpublish_result: Dict, 
                         submodule_results: Dict, completion_results: Dict = None) -> Dict:
        """Generate migration summary."""
        summary = {
            'project_analyzed': structure.get('success', False),
            'gradle_platform_detected': structure.get('is_gradle_platform', False),
            'total_gradle_files': len(structure.get('gradle_files', [])),
            'settings_updated': settings_result.get('success', False),
            'root_build_processed': root_build_result.get('success', False),
            'nexus_removed_from_root': root_build_result.get('nexus_removed', False),
            'artifactory_added_to_root': root_build_result.get('artifactory_added', False),
            'hzpublish_setup': hzpublish_result.get('success', False),
            'submodules_processed': submodule_results.get('processed_files', 0),
            'submodules_failed': submodule_results.get('failed_files', 0)
        }
        
        # Overall success
        if completion_results:
            summary['jenkinsfile_replaced'] = completion_results.get('success', False)
            summary['jenkinsfile_cleanup'] = completion_results.get('jenkinsfile_cleanup', {}).get('success', False)
            
            summary['overall_success'] = all([
                summary['project_analyzed'],
                summary['settings_updated'],
                summary['root_build_processed'],
                summary['hzpublish_setup'],
                summary['jenkinsfile_replaced']
            ])
        else:
            summary['overall_success'] = all([
                summary['project_analyzed'],
                summary['settings_updated'],
                summary['root_build_processed'],
                summary['hzpublish_setup']
            ])
        
        return summary


def main():
    """Test the migration workflow."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python gradle_migration_workflow.py <project_root> [enhanced_plugin_path]")
        return
    
    project_root = sys.argv[1]
    enhanced_plugin_path = sys.argv[2] if len(sys.argv) > 2 else "templates/artifactory-publishing-enhanced.gradle"
    
    if not os.path.exists(enhanced_plugin_path):
        print(f"Enhanced plugin template not found: {enhanced_plugin_path}")
        return
    
    workflow = GradleMigrationWorkflow(project_root)
    
    print(f"Running migration workflow for {project_root}...")
    results = workflow.run_migration_workflow(enhanced_plugin_path)
    
    print("\n" + "="*60)
    print("MIGRATION RESULTS")
    print("="*60)
    
    if results.get('is_gradle_platform'):
        print("⚠️  Gradle Platform detected - migration paused")
        print("Please provide specific Gradle Platform migration steps")
    elif results.get('success'):
        print("✅ Migration completed successfully!")
        
        summary = results.get('summary', {})
        print(f"\nSummary:")
        print(f"  📁 Project analyzed: {summary.get('project_analyzed', False)}")
        print(f"  ⚙️  Settings.gradle updated: {summary.get('settings_updated', False)}")
        print(f"  🔧 Root build.gradle processed: {summary.get('root_build_processed', False)}")
        print(f"  📦 hzPublish plugin setup: {summary.get('hzpublish_setup', False)}")
        print(f"  🏗️  Submodules processed: {summary.get('submodules_processed', 0)}/{summary.get('submodules_processed', 0) + summary.get('submodules_failed', 0)}")
        
        if summary.get('overall_success'):
            print("\n🎉 All migration steps completed successfully!")
        else:
            print("\n⚠️  Some issues were encountered during migration")
    else:
        print("❌ Migration failed")
        if 'error' in results:
            print(f"Error: {results['error']}")


if __name__ == "__main__":
    main()