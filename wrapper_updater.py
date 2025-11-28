import re
from pathlib import Path
from typing import Dict

def update_gradle_wrapper(wrapper_file: str, artifactory_base: str = 'https://artifactory.org.com/artifactory') -> Dict:
    """Update gradle-wrapper.properties distributionUrl to Artifactory.

    - Derives current Gradle version from existing distributionUrl
    - Writes new distributionUrl pointing to libs-release/com/baml/plat/gradle/wrapper/gradle-<version>-all.zip
    - Preserves other properties
    """
    result = {
        'success': False,
        'file_path': wrapper_file,
        'old_url': None,
        'new_url': None,
        'errors': []
    }

    try:
        p = Path(wrapper_file)
        if not p.exists():
            result['errors'].append('gradle-wrapper.properties not found')
            return result

        content = p.read_text(encoding='utf-8')

        # Find existing distributionUrl
        m = re.search(r'^\s*distributionUrl\s*=\s*(.+)$', content, re.MULTILINE)
        if not m:
            result['errors'].append('distributionUrl not found')
            return result

        old_url = m.group(1).strip()
        result['old_url'] = old_url

        # Extract version like gradle-6.8.2-all.zip
        vm = re.search(r'gradle-([\d\.]+)-all\.zip', old_url)
        if not vm:
            result['errors'].append('Unable to extract Gradle version from distributionUrl')
            return result
        version = vm.group(1)

        # Build new URL (escaped ':' for properties)
        new_url = f'{artifactory_base}/libs-release/com/baml/plat/gradle/wrapper/gradle-{version}-all.zip'
        # Properties file uses escaped colon in some generated files; Gradle supports unescaped https URL too.
        # To preserve style, replace ':' with '\:' if old_url used escapes.
        if '\\:' in old_url:
            new_url_prop = new_url.replace(':', '\\:')
        else:
            new_url_prop = new_url

        result['new_url'] = new_url

        # Replace in content preserving escaping and exact line formatting
        line_match = re.search(r'^(\s*distributionUrl\s*=\s*).+$', content, flags=re.MULTILINE)
        if not line_match:
            result['errors'].append('distributionUrl line not found during replace')
            return result
        prefix = line_match.group(1)
        start = line_match.start()
        end = line_match.end()
        new_line = prefix + new_url_prop
        new_content = content[:start] + new_line + content[end:]
        p.write_text(new_content, encoding='utf-8')

        result['success'] = True
        return result

    except Exception as e:
        result['errors'].append(str(e))
        return result