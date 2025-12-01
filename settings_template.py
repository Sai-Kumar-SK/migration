import re
import logging

# Template for settings.gradle repository configuration
# This template adds Artifactory repositories for dependency resolution

SETTINGS_GRADLE_TEMPLATE = '''
// Artifactory repositories for dependency resolution
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
        credentials {
            username = project.findProperty("artifactory_user") ?: System.getProperty("gradle.wrapperUser")
            password = project.findProperty("artifactory_password") ?: System.getProperty("gradle.wrapperPassword")
        }
        authentication {
            basic(BasicAuthentication)
        }
    }
}
'''

VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE = ""

STANDARD_SETTINGS_G6_TEMPLATE = '''
// Artifactory repositories for dependency resolution (Gradle 6.x)
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
        credentials {
            username = project.findProperty("artifactory_user") ?: System.getProperty("gradle.wrapperUser")
            password = project.findProperty("artifactory_password") ?: System.getProperty("gradle.wrapperPassword")
        }
        authentication {
            basic(BasicAuthentication)
        }
    }
}
'''

def get_version_catalog_settings_template() -> str:
    return VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE

def _normalize_base(artifactory_url: str) -> str:
    base = artifactory_url.rstrip('/')
    return base if base.endswith('/artifactory') else base + '/artifactory'

def get_settings_template(artifactory_url: str = "https://artifactory.org.com") -> str:
    base = _normalize_base(artifactory_url)
    return SETTINGS_GRADLE_TEMPLATE.replace('https://artifactory.org.com/artifactory', base)

log = logging.getLogger("horizon")

def append_repositories_to_settings(settings_file: str, artifactory_url: str = "https://artifactory.org.com") -> bool:
    try:
        template = get_settings_template(artifactory_url)
        
        # Read existing content
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        base = _normalize_base(artifactory_url)
        if base in content:
            log.info(f"Artifactory repositories already exist in {settings_file}")
            return False
            
        # Check if dependencyResolutionManagement block exists (Gradle 6+ feature)
        if 'dependencyResolutionManagement' in content:
            # Insert repositories inside existing dependencyResolutionManagement block
            if 'repositories {' in content:
                # Find the repositories block and insert before it
                repositories_match = re.search(r'(\s*)repositories\s*\{', content)
                if repositories_match:
                    indent = repositories_match.group(1)
                    # Insert our template before the existing repositories block
                    insertion_point = repositories_match.start()
                    new_content = content[:insertion_point] + template.strip() + '\n\n' + indent + content[insertion_point:]
                else:
                    # Fallback: append to end
                    new_content = content + '\n\n' + template.strip()
            else:
                
                dep_mgmt_end = content.rfind('}')
                if dep_mgmt_end != -1:
                    new_content = content[:dep_mgmt_end] + '\n    repositories {' + template.strip() + '\n    }\n' + content[dep_mgmt_end:]
                else:
                    new_content = content + '\n\ndependencyResolutionManagement {\n    repositories {' + template.strip() + '\n    }\n}'
        else:
            # Prepend at the beginning of the file
            new_content = template.strip() + '\n\n' + content
        
        # Write updated content
        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        log.info(f"Successfully updated {settings_file} with Artifactory repositories")
        return True
        
    except Exception as e:
        log.error(f"Error updating {settings_file}: {e}")
        return False

def append_repositories_to_settings_g6(settings_file: str, artifactory_url: str = "https://artifactory.org.com") -> bool:
    try:
        base = _normalize_base(artifactory_url)
        template = STANDARD_SETTINGS_G6_TEMPLATE.replace('https://artifactory.org.com/artifactory', base)
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        if base in content:
            log.info(f"Artifactory repositories already exist in {settings_file}")
            return False
        new_content = template.strip() + '\n\n' + content
        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        log.info(f"Successfully updated {settings_file} with Artifactory repositories (G6)")
        return True
    except Exception as e:
        log.error(f"Error updating {settings_file}: {e}")
        return False

# No CLI/testing code here; used by orchestrator only
