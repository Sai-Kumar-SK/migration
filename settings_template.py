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

def get_settings_template(artifactory_url: str = "https://artifactory.org.com") -> str:
    """Get the Groovy settings.gradle template (no Kotlin)."""
    template = SETTINGS_GRADLE_TEMPLATE
    template = template.replace('https://artifactory.org.com', artifactory_url)
    return template

def get_version_catalog_settings_template() -> str:
    return VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE

def append_repositories_to_settings(settings_file: str, artifactory_url: str = "https://artifactory.org.com") -> bool:
    """Append Artifactory repositories to settings.gradle file.
    
    Args:
        settings_file: Path to settings.gradle file
        artifactory_url: Base URL for Artifactory instance
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the appropriate template
        template = get_settings_template(artifactory_url)
        
        # Read existing content
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if Artifactory repositories already exist
        if 'artifactory.org.com' in content:
            print(f"Artifactory repositories already exist in {settings_file}")
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
                # Add repositories block inside dependencyResolutionManagement
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
            
        print(f"Successfully updated {settings_file} with Artifactory repositories")
        return True
        
    except Exception as e:
        print(f"Error updating {settings_file}: {e}")
        return False

# Example usage
if __name__ == "__main__":
    # Test templates
    print("Groovy DSL Template:")
    print(get_settings_template(is_kotlin_dsl=False))
    
    print("\nKotlin DSL Template:")
    print(get_settings_template(is_kotlin_dsl=True))