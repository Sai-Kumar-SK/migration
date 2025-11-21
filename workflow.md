```mermaid
flowchart TD
    A[Start] --> B[Parse CLI args]
    B --> C[Load repositories (--git-urls | --git-file)]
    C --> D{For each repo}
    D --> E[Clone via SSH]
    E --> F[Create/checkout branch<br/>--branch-name (default: horizon-migration)]
    F --> G[Analyze project]
    G --> H{Gradle Platform?}
    H -->|Yes| I[Stop: platform flow pending<br/>No file changes]
    H -->|No| J[Prepend repositories block<br/>to line 1 of settings.gradle]
    J --> K[Update gradle-wrapper.properties<br/>distributionUrl → Artifactory<br/><small>Version derived from Nexus URL</small>]
    K --> L[Verify dependency resolution<br/>gradle(w) dependencies --refresh-dependencies --no-daemon]
    L -->|OK| M[Commit changes<br/>Push to origin/<branch-name>]
    L -->|Fail| N[Abort commit<br/>Report error (do not push)]
    M --> O[Next repo]
    N --> O
    O --> P[Summarize results]
```