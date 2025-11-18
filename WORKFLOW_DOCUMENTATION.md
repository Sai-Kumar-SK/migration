# Gradle Nexus to Artifactory Migration - Comprehensive Workflow

## Overview
This workflow provides a complete solution for migrating Gradle projects from Nexus to Artifactory with proper project structure analysis and step-by-step migration process.

## Workflow Components

### 1. Gradle Project Parser (`gradle_parser.py`)
- **Purpose**: Analyzes project structure and detects Gradle Platform usage
- **Key Features**:
  - Finds all `.gradle` and `.gradle.kts` files in the project
  - Detects Gradle Platform by checking for `libs.versions.toml`
  - Looks for `plasmaGradlePlugins` in the version catalog
  - Analyzes build files for Nexus references
  - Identifies root vs submodule build files

### 2. Settings.gradle Template (`settings_template.py`)
- **Purpose**: Provides templated configuration for Artifactory repositories
- **Features**:
  - Supports both Groovy DSL and Kotlin DSL
  - Handles `dependencyResolutionManagement` blocks (Gradle 6+)
  - Configurable Artifactory URL
  - Proper credential handling with fallback to gradle wrapper properties

### 3. Nexus Removal Logic (`nexus_remover.py`)
- **Purpose**: Removes all Nexus references from build files
- **Capabilities**:
  - Removes Nexus plugin classpath declarations
  - Cleans up Nexus credential configurations
  - Removes `ext` blocks with Nexus variables
  - Eliminates Nexus plugin applications
  - Removes wrapper blocks with Nexus distribution URLs
  - Adds jfrog.artifactory plugin to root build.gradle

### 4. hzPublish Plugin Setup (`hzpublish_setup.py`)
- **Purpose**: Sets up the custom publishing plugin in buildSrc
- **Features**:
  - Creates proper buildSrc directory structure
  - Copies enhanced plugin template to `buildSrc/src/main/groovy/hzPublish.gradle`
  - Creates `HzPublishPlugin` class for plugin application
  - Configures buildSrc build.gradle for plugin development

### 5. Migration Workflow (`gradle_migration_workflow.py`)
- **Purpose**: Orchestrates the complete migration process
- **Steps**:
  1. **Project Analysis**: Parse project structure and detect Gradle Platform
  2. **Settings Update**: Add Artifactory repositories to settings.gradle
  3. **Root Build Processing**: Remove Nexus and add Artifactory plugin
  4. **Plugin Setup**: Configure hzPublish plugin in buildSrc
  5. **Submodule Processing**: Apply hzPublish plugin to submodule build files

### 6. Enhanced Main Script (`enhanced_gradle_migrator.py`)
- **Purpose**: Main entry point with parallel processing support
- **Features**:
  - SSH-based git cloning
  - Parallel processing of 20-30 repositories
  - Comprehensive logging and error handling
  - Detailed migration reports
  - Gradle Platform detection with workflow pause

## Migration Workflow Steps

### Step 1: Post Git Clone Analysis
```bash
python gradle_parser.py /path/to/cloned/repo
```
- Finds all `.gradle` files and `gradle-wrapper.properties`
- Detects if project uses Gradle Platform
- Analyzes Nexus usage in build files

### Step 2: Gradle Platform Detection
**If Gradle Platform is detected**:
- Workflow pauses and waits for specific Gradle Platform instructions
- Simpler migration steps will be used

**If Standard Gradle is detected**:
- Proceeds with full migration workflow
- Prints: "Standard Gradle project detected - starting migration"

### Step 3: Settings.gradle Update
Adds Artifactory repositories:
```gradle
repositories {
    maven {
        url = 'https://artifactory.org.com/artifactory/libs-release'
        credentials {
            username = project.findProperty("artifactory_user") ?: System.getProperty("gradle.wrapperUser")
            password = project.findProperty("artifactory_password") ?: System.getProperty("gradle.wrapperPassword")
        }
        authentication {
            basic(BasicAuthentication)
        }
    }
    maven {
        url = 'https://artifactory.org.com/artifactory/libs-snapshot'
        // ... similar configuration
    }
}
```

### Step 4: Root build.gradle Processing
**Removes Nexus references**:
- `classpath "com.bmuschko:gradle-nexus-plugin:2.3.1"`
- `def nexusCredentialsLocation = System.properties['user.home'] + "/.secure/nexus.credentials"`
- `ext` blocks with Nexus variables
- `uploadArchives.enabled = false`
- `apply plugin: "com.bmuschko.nexus"`
- `nexus` configuration blocks
- `wrapper` blocks with Nexus distribution URLs

**Adds Artifactory plugin**:
```gradle
plugins {
    id 'com.jfrog.artifactory' version '4.28.2'
}
```

### Step 5: hzPublish Plugin Setup
- Copies `artifactory-publishing-enhanced.gradle` to `buildSrc/src/main/groovy/hzPublish.gradle`
- Creates `HzPublishPlugin` class for plugin application
- Sets up buildSrc build.gradle for plugin development

### Step 6: Submodule build.gradle Processing
**Applies hzPublish plugin**:
```gradle
plugins {
    id 'hzPublish'
}
```

**Removes uploadArchives.enabled = true**

## Usage Examples

### Single Repository Migration
```bash
python enhanced_gradle_migrator.py \
  --git-urls git@github.com:org/repo.git \
  --artifactory-username myuser \
  --artifactory-password mypass \
  --commit-message "Migrate from Nexus to Artifactory"
```

### Multiple Repository Migration (Parallel)
```bash
python enhanced_gradle_migrator.py \
  --git-file repos.txt \
  --artifactory-username myuser \
  --artifactory-password mypass \
  --max-workers 20 \
  --commit-message "Migrate from Nexus to Artifactory"
```

### Testing Individual Components
```bash
# Test project parser
python gradle_parser.py /path/to/project

# Test Nexus removal
python nexus_remover.py /path/to/build.gradle

# Test complete workflow
python gradle_migration_workflow.py /path/to/project
```

## Key Features

1. **Gradle Platform Detection**: Automatically detects and handles Gradle Platform projects
2. **Comprehensive Nexus Removal**: Removes all types of Nexus references from build files
3. **Template-Based Configuration**: Uses templates for easy customization
4. **Parallel Processing**: Handles 20-30 repositories concurrently
5. **Detailed Reporting**: Provides comprehensive migration reports
6. **Error Handling**: Robust error handling and logging throughout
7. **SSH Git Support**: Uses SSH URLs with existing SSH key setup

## Next Steps

The workflow is now ready for your Gradle Platform specific instructions. When you're ready, please provide the steps for Gradle Platform projects, and I'll implement those as well.