# Gradle Nexus to Artifactory Migration Tool

This tool automates the migration of Gradle projects from Nexus to Artifactory.

## Features

- **Parallel Processing**: Migrate 20-30 repositories simultaneously
- **Custom Gradle Plugin**: Automatically creates and applies Artifactory publishing plugin
- **Nexus Cleanup**: Removes all Nexus references from build files
- **Settings Update**: Updates settings.gradle for Artifactory dependency resolution
- **Jenkinsfile Replacement**: Replaces Jenkinsfile with Artifactory-enabled version
- **Comprehensive Reporting**: Generates detailed migration reports
- **SSH Git Support**: Leverages existing SSH key setup

## Installation

1. Install Python 3.7+
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make the script executable:
```bash
chmod +x gradle_artifactory_migrator.py
```

## Usage

### Single Repository
```bash
python enhanced_gradle_migrator.py \
  --git-urls git@github.com:your-org/your-repo.git \
  --commit-message "Migrate to Artifactory"
```

### Multiple Repositories
```bash
python enhanced_gradle_migrator.py \
  --git-urls git@github.com:your-org/repo1.git git@github.com:your-org/repo2.git \
  --commit-message "Migrate to Artifactory" \
  --max-workers 20
```

### Using Repository List File
```bash
# Create a file with repository URLs (one per line)
echo "git@github.com:your-org/repo1.git" > repos.txt
echo "git@github.com:your-org/repo2.git" >> repos.txt

python enhanced_gradle_migrator.py \
  --git-file repos.txt \
  --commit-message "Migrate to Artifactory" \
  --max-workers 30
```

## Parameters

- `--git-urls`: Multiple repository URLs (space-separated)
- `--git-file`: File containing repository URLs (one per line)
- `--repo-urls`: Alternative flag for repository URLs
- `--repo-file`: Alternative flag for repository list file
- `--commit-message`: Commit message for the migration (default: "Migrate from Nexus to Artifactory")
- `--artifactory-url`: Artifactory base URL (optional; defaults to `https://artifactory.org.com`)
- `--artifactory-repo-key`: Artifactory repository key (optional)
- `--max-workers`: Maximum number of parallel workers (default: 10)
- `--temp-dir`: Temporary directory for cloning repositories
- `--report-file`: Output file for migration report (default: migration_report.md)
- `--branch-name`: Branch name used for migration changes (optional; default: `horizon-migration`)

## What the Tool Does

1. **Clones Repository**: Creates a temporary clone of the repository
2. **Creates Publishing Plugin**: Generates a custom Artifactory publishing plugin in `buildSrc/`
3. **Removes Nexus References**: Cleans all Nexus-related configurations from build files
4. **Updates Settings**: Modifies `settings.gradle` to resolve dependencies from Artifactory
5. **Updates Build Files**: Applies the custom publishing plugin to all `build.gradle` files
6. **Replaces Jenkinsfile**: Updates Jenkinsfile with Artifactory publishing stages
7. **Commits and Pushes**: Creates a new branch and pushes changes

## Customization

### Custom Plugin Template
Edit `templates/artifactory.gradle` to customize the publishing plugin.

### Custom Jenkinsfile Template
Edit `templates/Jenkinsfile.enhanced` to customize the Jenkins pipeline.

## Credential & URL Sourcing

- The tool does not require passing Artifactory credentials or repo keys as CLI arguments.
- Dependency resolution templates reference Gradle properties:
  - `project.findProperty("artifactory_user")`
  - `project.findProperty("artifactory_password")`
  - Fallbacks: `System.getProperty("gradle.wrapperUser")` and `System.getProperty("gradle.wrapperPassword")`
- Publishing credentials are managed within the Gradle plugin and Jenkinsfile template.
- Optionally, you may override the Artifactory base URL via `--artifactory-url`.

## Logging

The tool creates a detailed `migration.log` file with all operations and errors.

## Error Handling

- Failed migrations are logged and reported
- Temporary directories are automatically cleaned up
- Individual repository failures don't affect other migrations
- Detailed error messages help with troubleshooting

## Scaling

For migrating hundreds of repositories:
- Increase `--max-workers` based on your system capabilities
- Use `--repos-file` for batch processing
- Monitor system resources during migration
- Consider running in batches for very large migrations