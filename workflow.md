```mermaid
flowchart TD
    A[Start] --> B[Parse CLI args]
    B --> C[Load repositories (--git-urls | --git-file)]
    C --> D{For each repo}
    D --> E[Clone via SSH]
    E --> F[Create/checkout branch<br/>--branch-name (default: horizon-migration)]
    F --> G[Analyze project]
    G --> H{Gradle Platform?}
    H -->|Yes| I[Gradle Platform Path]
    H -->|No| Q{libs.versions.toml exists?}
    Q -->|Yes| R[Version Catalog (non-plasma) Path]
    Q -->|No| J[Standard Path]

    %% Standard Path
    J --> K[Prepend repositories block<br/>to line 1 of settings.gradle]
    K --> L[Update gradle-wrapper.properties<br/>distributionUrl → Artifactory<br/><small>Version derived from Nexus URL</small>]
    L --> S[Verify dependency resolution<br/>gradle(w) dependencies --refresh-dependencies --no-daemon]
    S -->|OK| M[Commit changes<br/>Push to origin/<branch-name>]
    S -->|Fail| N[Abort commit<br/>Report error (do not push)]

    %% Gradle Platform Path
    I --> I1[Update gradle-wrapper.properties]
    I1 --> I2[Replace plugin-repositories-nexus → repositories-artifactory in libs.versions.toml (only if present)]
    I2 --> I3[Replace buildSrc/build.gradle implementation libs.plugin.repositories.nexus → .artifactory (only if present)]
    I3 --> I4[Replace id 'ops.plasma.repositories-nexus' → 'ops.plasma.repositories-artifactory' in buildSrc/src/main/groovy/*.lib.groovy]
    I4 --> I5[Replace buildSrc/settings.gradle with VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE]
    I5 --> I6[Clean root settings.gradle (remove pluginManagement, dependencyResolutionManagement, gradle.allprojects)]
    I6 --> I7[Verify dependency resolution]
    I7 -->|OK| M
    I7 -->|Fail| N

    %% Version Catalog (non-plasma) Path
    R --> R1[Update gradle-wrapper.properties]
    R1 --> R2[Replace buildSrc/settings.gradle with VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE]
    R2 --> R3[Clean root settings.gradle (remove pluginManagement, dependencyResolutionManagement, gradle.allprojects)]
    R3 --> R4[Verify dependency resolution]
    R4 -->|OK| M
    R4 -->|Fail| N
    M --> O[Next repo]
    N --> O
    M --> O[Next repo]
    N --> O
    O --> P[Summarize results]
```