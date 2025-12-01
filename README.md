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

## Usage (Horizon Standard Migrator)

### Single Repository
```bash
python horizon_standard_migrator.py \
  --git-urls ssh://git@scm.org.com/spk/your-repo.git \
  --commit-message "Migrate settings + wrapper to Artifactory" \
  --branch-name horizon-migration \
  --artifactory-url https://artifactory.org.com/artifactory
```

### Multiple Repositories (from file)
```bash
# Create a file with repository URLs (one per line)
echo "ssh://git@scm.org.com/spk/repo1.git" > repos.txt
echo "ssh://git@scm.org.com/spk/repo2.git" >> repos.txt

python horizon_standard_migrator.py \
  --git-file repos.txt \
  --commit-message "Migrate settings + wrapper to Artifactory" \
  --branch-name horizon-migration \
  --max-workers 20 \
  --artifactory-url https://artifactory.org.com/artifactory
```

### Behavior (High Level)
- Clones via SSH and creates/checkout branch.
- Analyzes project and picks one path: Standard, Gradle Platform, or Version Catalog.
- Updates settings/wrapper (or platform files), then updates Jenkinsfile(s).
- Verifies dependencies; commits and pushes on success.
- Uses per-repo cache (`-g <cache-dir>`) only when `--git-file` is provided.

### Dependency Log Aggregator

After running the standard migration, aggregate unresolved dependencies across all per-repo logs.

#### Usage
```bash
# Default scans your system temp directory and appends to aggregated log in the same location
python aggregate_dependency_logs.py

# Specify logs directory and aggregated output file
python aggregate_dependency_logs.py \
  --logs-dir /tmp \
  --output-file /tmp/dependency-resolution-aggregated.log
```

#### Behavior
- Scans `dependency-resolution-*.log` files in the specified directory
- Extracts unresolved dependencies and appends unique coordinates to the aggregated file
- Avoids duplicates across runs by skipping already-recorded `group:name:version` lines
- Records per-entry repos seen in that run

#### Log Locations
- Linux/macOS: `/tmp`
- Windows: `C:\\Users\\<username>\\AppData\\Local\\Temp`

## Arguments (horizon_standard_migrator.py)

- `--git-urls`: Repository URLs (space-separated)
- `--git-file`: File with repository URLs (one per line)
- `--branch-name`: Branch name (default: `horizon-migration`)
- `--commit-message`: Commit message (default: "Migrate settings.gradle and wrapper to Artifactory")
- `--artifactory-url`: Artifactory base URL (default: `https://artifactory.org.com/artifactory`)
- `--max-workers`: Parallel workers (default: 10)
- `--temp-dir`: Temporary directory root
- `--java-home-override`: JAVA_HOME override for Gradle invocation
- `--jenkinsfiles`: Jenkinsfile paths to update (default: `Jenkinsfile.build.groovy`)
- `--verbose`: Enable verbose logging

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

## Wrapper Credentials (Local)

- For wrapper bootstrap authentication, set once:
  - `JAVA_TOOL_OPTIONS=-Dgradle.wrapperUser=<username> -Dgradle.wrapperPassword=<password>`
- This is read by the wrapper JVM regardless of `-g` usage.

## Logging

- Detailed log written to the console; dependency verification logs are saved to the system temp directory as `dependency-resolution-<spk>-<repo>.log`.

## Error Handling

- Failed migrations are logged and reported
- Temporary directories are automatically cleaned up
- Individual repository failures don't affect other migrations
- Detailed error messages help with troubleshooting

## Scaling

- Increase `--max-workers` based on your system capabilities.
- Use `--git-file` for batch processing; `-g <cache-dir>` is applied per repo to avoid lock contention.
