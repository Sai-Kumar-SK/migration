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
python gradle_artifactory_migrator.py \
  --git-url git@github.com:your-org/your-repo.git \
  --commit-message "Migrate to Artifactory" \
  --artifactory-url https://your-artifactory.com/artifactory \
  --artifactory-repo-key libs-release-local \
  --artifactory-username your-username \
  --artifactory-password your-password
```

### Multiple Repositories
```bash
python gradle_artifactory_migrator.py \
  --repos git@github.com:your-org/repo1.git git@github.com:your-org/repo2.git \
  --commit-message "Migrate to Artifactory" \
  --artifactory-url https://your-artifactory.com/artifactory \
  --artifactory-repo-key libs-release-local \
  --artifactory-username your-username \
  --artifactory-password your-password \
  --max-workers 20
```

### Using Repository List File
```bash
# Create a file with repository URLs (one per line)
echo "git@github.com:your-org/repo1.git" > repos.txt
echo "git@github.com:your-org/repo2.git" >> repos.txt

python gradle_artifactory_migrator.py \
  --repos-file repos.txt \
  --commit-message "Migrate to Artifactory" \
  --artifactory-url https://your-artifactory.com/artifactory \
  --artifactory-repo-key libs-release-local \
  --artifactory-username your-username \
  --artifactory-password your-password \
  --max-workers 30
```

## Parameters

- `--git-url`: Single git repository URL
- `--repos`: Multiple repository URLs (space-separated)
- `--repos-file`: File containing repository URLs (one per line)
- `--commit-message`: Commit message for the migration (default: "Migrate from Nexus to Artifactory")
- `--artifactory-url`: Artifactory base URL (required)
- `--artifactory-repo-key`: Artifactory repository key (required)
- `--artifactory-username`: Artifactory username (required)
- `--artifactory-password`: Artifactory password (required)
- `--max-workers`: Maximum number of parallel workers (default: 10)
- `--temp-dir`: Temporary directory for cloning repositories
- `--report-file`: Output file for migration report (default: migration_report.txt)

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
Edit `templates/artifactory-publishing.gradle` to customize the publishing plugin.

### Custom Jenkinsfile Template
Edit `templates/Jenkinsfile.artifactory` to customize the Jenkins pipeline.

## Environment Variables

You can also use environment variables for Artifactory configuration:
- `ARTIFACTORY_URL`
- `ARTIFACTORY_REPO_KEY`
- `ARTIFACTORY_USERNAME`
- `ARTIFACTORY_PASSWORD`

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