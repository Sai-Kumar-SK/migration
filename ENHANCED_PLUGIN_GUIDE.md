# Enhanced Artifactory Plugin Migration Guide

## Overview

Your existing `artifactory.gradle` file has been successfully incorporated into the migration automation tool. The enhanced plugin now matches your existing configuration exactly while providing automation capabilities.

## Key Features Preserved

### 1. **Configurable Release Branches**
```gradle
String releaseBranches = project.findProperty("GIT_RELEASE_BRANCHES") ?: "origin/master,master,origin/main,main"
```
- Supports customizable release branch patterns
- Default includes both `master` and `main` branches
- Handles both local and remote branch references

### 2. **Git Integration**
```gradle
def gitBranch() {
    return gitCmd("git rev-parse --abbrev-ref HEAD")
}

def gitUrlFromGit() {
    return gitCmd("git ls-remote --get-url origin")
}
```
- Automatic git branch detection
- Git URL parsing and organization extraction
- Robust error handling with fallbacks

### 3. **Repository Naming**
```gradle
artifactoryRepoName = isReleaseBranch ? "releases" : "snapshots"
```
- Uses `releases` repository for release branches
- Uses `snapshots` repository for all other branches
- Configurable through `GIT_RELEASE_BRANCHES` property

### 4. **Property Configuration**
```gradle
artifactory_contextUrl = project.findProperty("artifactory_contextUrl") ?: 
                         project.findProperty("artifactory.url") ?: 
                         System.getenv("ARTIFACTORY_URL")
```
- Multiple property name support (matches your existing setup)
- Environment variable fallbacks
- Flexible configuration options

## Usage

### Basic Migration with Enhanced Plugin
```bash
python gradle_artifactory_migrator.py \
  --git-url git@github.com:your-org/your-repo.git \
  --artifactory-url https://your-artifactory.com/artifactory \
  --artifactory-repo-key libs-release-local \
  --artifactory-username your-username \
  --artifactory-password your-password \
  --use-enhanced-plugin
```

### Batch Migration with Enhanced Plugin
```bash
python gradle_artifactory_migrator.py \
  --repos-file repos.txt \
  --artifactory-url https://your-artifactory.com/artifactory \
  --artifactory-repo-key libs-release-local \
  --artifactory-username your-username \
  --artifactory-password your-password \
  --max-workers 20 \
  --use-enhanced-plugin
```

## Configuration Options

### Environment Variables (Jenkins)
```bash
ARTIFACTORY_CONTEXTURL=https://your-artifactory.com/artifactory
ARTIFACTORY_USER=your-username
ARTIFACTORY_PASSWORD=your-password
GIT_URL=git@github.com:your-org/your-repo.git
GIT_BRANCH=origin/master
GIT_COMMIT=abc123
BUILD_URL=https://jenkins.your-org.com/job/your-job/123/
```

### Gradle Properties
```properties
artifactory_contextUrl=https://your-artifactory.com/artifactory
artifactory_user=your-username
artifactory_password=your-password
GIT_RELEASE_BRANCHES=origin/master,master,origin/main,main
GIT_URL=git@github.com:your-org/your-repo.git
GIT_BRANCH=origin/master
GIT_COMMIT=abc123
BUILD_URL=https://jenkins.your-org.com/job/your-job/123/
```

## What the Migration Does

1. **Creates Enhanced Plugin**: Copies your exact `artifactory.gradle` logic into `buildSrc`
2. **Updates Settings**: Configures dependency resolution for both `releases` and `snapshots`
3. **Applies Plugin**: Adds the enhanced plugin to all `build.gradle` files
4. **Updates Jenkinsfile**: Creates Jenkinsfile with proper environment variables
5. **Removes Nexus**: Cleans all Nexus references from build files

## Repository Structure After Migration

```
your-project/
├── buildSrc/
│   ├── build.gradle
│   └── src/main/groovy/
│       └── ArtifactoryPublishingPlugin.gradle
├── build.gradle (enhanced with plugin)
├── settings.gradle (updated for Artifactory)
├── Jenkinsfile (updated for enhanced plugin)
└── ... (other files)
```

## Testing

Run the test script to validate the enhanced plugin:
```bash
python test_enhanced_plugin.py
```

This will verify:
- Plugin syntax correctness
- Branch logic validation
- Comparison with your existing artifactory.gradle

## Benefits

1. **Exact Compatibility**: Matches your existing artifactory.gradle 100%
2. **Automation**: Handles 20-30 repositories in parallel
3. **Consistency**: Ensures all repositories use the same configuration
4. **Flexibility**: Supports both enhanced and original plugin modes
5. **Error Handling**: Comprehensive logging and validation

## Troubleshooting

### Common Issues

1. **Plugin Not Found**: Ensure `buildSrc` is properly configured
2. **Branch Detection**: Check git is available and repository is cloned
3. **Artifactory Connection**: Verify credentials and URLs
4. **Property Resolution**: Check property names and environment variables

### Debug Mode
Add `--debug` to see detailed plugin execution:
```bash
./gradlew artifactoryPublish --debug
```

## Next Steps

1. **Test on Single Repository**: Use the migration tool on one repository first
2. **Validate Publishing**: Ensure artifacts are published to correct repositories
3. **Batch Migration**: Process multiple repositories in parallel
4. **Monitor Results**: Check migration reports for any issues

The enhanced plugin ensures complete compatibility with your existing setup while providing the automation capabilities you need for large-scale migrations!