#!/usr/bin/env python3
"""
Enhanced Gradle Nexus to Artifactory Migration Automation Script

This script provides a comprehensive workflow for migrating Gradle projects from Nexus to Artifactory
with proper project structure analysis, Nexus removal, and Artifactory integration.
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
from dataclasses import dataclass
from datetime import datetime

# Import new workflow modules
from gradle_migration_workflow import GradleMigrationWorkflow
from gradle_parser import GradleProjectParser

@dataclass
class MigrationResult:
    """Result of a repository migration"""
    repo_url: str
    success: bool
    message: str
    changes: List[str]
    gradle_platform_detected: bool = False
    migration_details: Optional[Dict] = None

class EnhancedGradleArtifactoryMigrator:
    """Enhanced migrator with comprehensive workflow support"""
    
    def __init__(self, artifactory_url: str,
                 artifactory_repo_key: Optional[str] = None,
                 max_workers: int = 10, temp_dir: Optional[str] = None,
                 use_enhanced_plugin: bool = True):
        self.artifactory_url = artifactory_url
        self.artifactory_repo_key = artifactory_repo_key
        self.max_workers = max_workers
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.use_enhanced_plugin = use_enhanced_plugin
        
        # Setup logging
        self.setup_logging()
        
        # Load templates
        self.load_templates()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('gradle_migration.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_templates(self):
        """Load plugin templates"""
        template_dir = Path(__file__).parent / "templates"
        
        if self.use_enhanced_plugin:
            self.plugin_template_path = template_dir / "artifactory-publishing-enhanced.gradle"
        else:
            self.plugin_template_path = template_dir / "artifactory-publishing.gradle"
        
        self.jenkinsfile_template_path = template_dir / "Jenkinsfile.enhanced"
    
    def clone_repository(self, repo_url: str, work_dir: Path) -> Tuple[bool, str]:
        """Clone a git repository"""
        try:
            self.logger.info(f"Cloning repository: {repo_url}")
            
            # Use SSH for cloning (assuming SSH key is set up)
            if not repo_url.startswith(('git@', 'ssh://')):
                # Convert HTTPS to SSH format
                if 'github.com' in repo_url:
                    repo_name = repo_url.split('/')[-1].replace('.git', '')
                    org_name = repo_url.split('/')[-2]
                    repo_url = f"git@github.com:{org_name}/{repo_name}.git"
                elif 'gitlab' in repo_url:
                    repo_path = repo_url.split('gitlab.com')[-1].replace('.git', '')
                    repo_url = f"git@gitlab.com:{repo_path}.git"
            
            result = subprocess.run(
                ['git', 'clone', repo_url, str(work_dir)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully cloned {repo_url}")
                return True, "Repository cloned successfully"
            else:
                error_msg = f"Failed to clone {repo_url}: {result.stderr}"
                self.logger.error(error_msg)
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = f"Timeout while cloning {repo_url}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error cloning {repo_url}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def run_comprehensive_migration(self, work_dir: Path) -> MigrationResult:
        """Run the new comprehensive migration workflow"""
        try:
            self.logger.info("Starting comprehensive migration workflow")
            
            # Initialize workflow
            workflow = GradleMigrationWorkflow(
                str(work_dir), 
                artifactory_url=self.artifactory_url
            )
            
            # Run migration workflow
            migration_results = workflow.run_migration_workflow(str(self.plugin_template_path))
            
            if migration_results.get('is_gradle_platform'):
                return MigrationResult(
                    repo_url=str(work_dir),
                    success=False,
                    message="Gradle Platform detected - manual intervention required",
                    changes=[],
                    gradle_platform_detected=True,
                    migration_details=migration_results
                )
            
            # Check if migration was successful
            if migration_results.get('success', False):
                summary = migration_results.get('summary', {})
                changes = [
                    f"Settings.gradle updated: {summary.get('settings_updated', False)}",
                    f"Root build.gradle processed: {summary.get('root_build_processed', False)}",
                    f"Nexus references removed: {summary.get('nexus_removed_from_root', False)}",
                    f"Artifactory plugin added: {summary.get('artifactory_added_to_root', False)}",
                    f"hzPublish plugin setup: {summary.get('hzpublish_setup', False)}",
                    f"Submodules processed: {summary.get('submodules_processed', 0)}",
                    f"Submodules failed: {summary.get('submodules_failed', 0)}"
                ]
                
                return MigrationResult(
                    repo_url=str(work_dir),
                    success=True,
                    message="Comprehensive migration completed successfully",
                    changes=changes,
                    gradle_platform_detected=False,
                    migration_details=migration_results
                )
            else:
                return MigrationResult(
                    repo_url=str(work_dir),
                    success=False,
                    message="Comprehensive migration failed",
                    changes=[],
                    gradle_platform_detected=False,
                    migration_details=migration_results
                )
                
        except Exception as e:
            error_msg = f"Error in comprehensive migration: {str(e)}"
            self.logger.error(error_msg)
            return MigrationResult(
                repo_url=str(work_dir),
                success=False,
                message=error_msg,
                changes=[]
            )
    
    def migrate_repository_legacy(self, repo_url: str, commit_message: str) -> MigrationResult:
        """Legacy migration method for backward compatibility"""
        work_dir = Path(self.temp_dir) / f"gradle_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Clone repository
            success, message = self.clone_repository(repo_url, work_dir)
            if not success:
                return MigrationResult(repo_url, False, message, [])
            
            # Run comprehensive migration
            result = self.run_comprehensive_migration(work_dir)
            result.repo_url = repo_url
            
            # If migration was successful, commit and push changes
            if result.success:
                self.commit_and_push_changes(work_dir, commit_message)
            
            return result
            
        except Exception as e:
            error_msg = f"Error migrating {repo_url}: {str(e)}"
            self.logger.error(error_msg)
            return MigrationResult(repo_url, False, error_msg, [])
            
        finally:
            # Cleanup temporary directory
            if work_dir.exists():
                shutil.rmtree(work_dir)
    
    def commit_and_push_changes(self, work_dir: Path, commit_message: str) -> Tuple[bool, str]:
        """Commit and push changes to repository"""
        try:
            # Configure git user (use environment variables or defaults)
            git_user = os.environ.get('GIT_USER', 'Gradle Migration Bot')
            git_email = os.environ.get('GIT_EMAIL', 'migration@bot.com')
            
            # Set git config
            subprocess.run(['git', 'config', 'user.name', git_user], cwd=work_dir, check=True)
            subprocess.run(['git', 'config', 'user.email', git_email], cwd=work_dir, check=True)
            
            # Add all changes
            subprocess.run(['git', 'add', '.'], cwd=work_dir, check=True)
            
            # Check if there are changes to commit
            result = subprocess.run(['git', 'status', '--porcelain'], cwd=work_dir, capture_output=True, text=True)
            if not result.stdout.strip():
                self.logger.info("No changes to commit")
                return True, "No changes to commit"
            
            # Commit changes
            subprocess.run(['git', 'commit', '-m', commit_message], cwd=work_dir, check=True)
            
            # Push changes
            subprocess.run(['git', 'push'], cwd=work_dir, check=True)
            
            self.logger.info("Changes committed and pushed successfully")
            return True, "Changes committed and pushed successfully"
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Git operation failed: {e.stderr}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error committing changes: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def migrate_repositories_parallel(self, repo_urls: List[str], commit_message: str) -> List[MigrationResult]:
        """Migrate multiple repositories in parallel"""
        self.logger.info(f"Starting parallel migration of {len(repo_urls)} repositories")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all migration tasks
            future_to_repo = {
                executor.submit(self.migrate_repository_legacy, repo_url, commit_message): repo_url 
                for repo_url in repo_urls
            }
            
            # Process completed tasks
            for future in as_completed(future_to_repo):
                repo_url = future_to_repo[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        self.logger.info(f"✅ Successfully migrated {repo_url}")
                    else:
                        self.logger.error(f"❌ Failed to migrate {repo_url}: {result.message}")
                        
                except Exception as e:
                    error_result = MigrationResult(repo_url, False, f"Exception: {str(e)}", [])
                    results.append(error_result)
                    self.logger.error(f"❌ Exception migrating {repo_url}: {str(e)}")
        
        return results
    
    def generate_report(self, results: List[MigrationResult]) -> str:
        """Generate migration report"""
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        gradle_platform_count = sum(1 for r in results if r.gradle_platform_detected)
        
        report = f"""
# Gradle Nexus to Artifactory Migration Report
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total repositories: {len(results)}
- Successfully migrated: {successful}
- Failed migrations: {failed}
- Gradle Platform detected: {gradle_platform_count}

## Detailed Results

"""
        
        for result in results:
            status_icon = "✅" if result.success else "❌"
            if result.gradle_platform_detected:
                status_icon = "⚠️"
            
            report += f"### {status_icon} {result.repo_url}\n"
            report += f"**Status:** {'Success' if result.success else 'Failed'}\n"
            report += f"**Message:** {result.message}\n"
            
            if result.changes:
                report += "**Changes made:**\n"
                for change in result.changes:
                    report += f"- {change}\n"
            
            if result.migration_details:
                report += "**Migration Details:**\n"
                report += f"```json\n{json.dumps(result.migration_details, indent=2)}\n```\n"
            
            report += "\n"
        
        return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Migrate Gradle projects from Nexus to Artifactory')
    parser.add_argument('--repo-urls', nargs='+', help='List of repository URLs to migrate')
    parser.add_argument('--repo-file', help='File containing repository URLs (one per line)')
    parser.add_argument('--git-urls', nargs='+', help='Git repository URLs (SSH format preferred)')
    parser.add_argument('--git-file', help='File containing git URLs (one per line)')
    parser.add_argument('--commit-message', default='Migrate from Nexus to Artifactory', 
                       help='Commit message for the migration')
    parser.add_argument('--artifactory-url', default='https://artifactory.org.com', 
                       help='Artifactory base URL')
    parser.add_argument('--artifactory-repo-key', help='Artifactory repository key (optional)')
    parser.add_argument('--max-workers', type=int, default=10, 
                       help='Maximum number of parallel workers')
    parser.add_argument('--temp-dir', help='Temporary directory for cloning')
    parser.add_argument('--report-file', default='migration_report.md', 
                       help='Output report file')
    parser.add_argument('--use-legacy-migration', action='store_true',
                       help='Use legacy migration method instead of comprehensive workflow')
    parser.add_argument('--use-enhanced-plugin', action='store_true', default=True,
                       help='Use enhanced plugin template (default: True)')
    
    args = parser.parse_args()
    
    # Collect repository URLs
    repo_urls = []
    
    if args.repo_urls:
        repo_urls.extend(args.repo_urls)
    if args.repo_file:
        with open(args.repo_file, 'r') as f:
            repo_urls.extend(line.strip() for line in f if line.strip())
    if args.git_urls:
        repo_urls.extend(args.git_urls)
    if args.git_file:
        with open(args.git_file, 'r') as f:
            repo_urls.extend(line.strip() for line in f if line.strip())
    
    if not repo_urls:
        print("Error: No repository URLs provided")
        parser.print_help()
        sys.exit(1)
    
    print(f"Starting migration for {len(repo_urls)} repositories...")
    
    # Initialize migrator
    migrator = EnhancedGradleArtifactoryMigrator(
        artifactory_url=args.artifactory_url,
        artifactory_repo_key=args.artifactory_repo_key,
        max_workers=args.max_workers,
        temp_dir=args.temp_dir,
        use_enhanced_plugin=args.use_enhanced_plugin
    )
    
    # Run migrations
    results = migrator.migrate_repositories_parallel(repo_urls, args.commit_message)
    
    # Generate and save report
    report = migrator.generate_report(results)
    with open(args.report_file, 'w') as f:
        f.write(report)
    
    print(f"\nMigration completed! Report saved to {args.report_file}")
    print(f"Successful: {sum(1 for r in results if r.success)}")
    print(f"Failed: {sum(1 for r in results if not r.success)}")
    print(f"Gradle Platform detected: {sum(1 for r in results if r.gradle_platform_detected)}")
    
    # Exit with appropriate code
    if any(not r.success for r in results):
        sys.exit(1)


if __name__ == '__main__':
    main()