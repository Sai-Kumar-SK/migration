# Artifactory Plugin Configuration Update

## Recent Changes Made

### 1. **Branch-Based Repository Selection**
The plugin now automatically determines the target Artifactory repository based on the current git branch:

- **master** or **main** branch → publishes to `libs-release`
- **any other branch** (develop, feature/*, release/*, etc.) → publishes to `libs-snapshot`

### 2. **Separated Concerns**
- **Dependency Resolution**: Handled through `settings.gradle` (read-only access to libs-release and libs-snapshot)
- **Publishing**: Handled through the custom plugin (branch-based target selection)

### 3. **Plugin Logic**
```groovy
private String determineTargetRepository(Project project) {
    try {
        def branchProcess = ['git', 'rev-parse', '--abbrev-ref', 'HEAD'].execute()
        branchProcess.waitFor()
        
        if (branchProcess.exitValue() == 0) {
            def currentBranch = branchProcess.text.trim()
            
            if (currentBranch == 'master' || currentBranch == 'main') {
                return 'libs-release'
            } else {
                return 'libs-snapshot'
            }
        } else {
            return 'libs-snapshot' // fallback
        }
    } catch (Exception e) {
        return 'libs-snapshot' // fallback
    }
}
```

### 4. **Updated Settings.gradle Configuration**
The `settings.gradle` now includes both repositories for dependency resolution:
```gradle
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        // Use libs-release for dependency resolution (read-only)
        maven {
            url '${artifactory_url}/libs-release'
            credentials { ... }
        }
        // Fallback to libs-snapshot for snapshot dependencies
        maven {
            url '${artifactory_url}/libs-snapshot'
            credentials { ... }
        }
        mavenCentral()
    }
}
```

### 5. **Jenkinsfile Updates**
- Removed hardcoded `ARTIFACTORY_REPO_KEY` environment variable
- Plugin automatically determines target repository
- Simplified publish command

## Benefits

1. **Automatic Branch-Based Publishing**: No manual configuration needed
2. **Clear Separation**: Dependency resolution vs publishing concerns separated
3. **Fallback Handling**: Graceful degradation if git branch detection fails
4. **Consistent Workflow**: Works the same way across all repositories
5. **CI/CD Friendly**: Works seamlessly with Jenkins and other CI systems

## Usage

No changes needed to the migration tool usage. The plugin will automatically:
- Detect the current git branch
- Choose the appropriate repository (libs-release or libs-snapshot)
- Publish artifacts to the correct location

## Testing

Run the test script to validate the branch logic:
```bash
python test_branch_simple.py
```

This will verify:
- Plugin syntax correctness
- Branch detection logic
- Repository selection logic
- No dependency resolution interference