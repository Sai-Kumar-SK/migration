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
        'enforced_default': False,
        'network_timeout_prev': None,
        'network_timeout_new': None,
        'network_timeout_added': False,
        'network_timeout_changed': False,
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

        # Extract version and distribution type like gradle-6.8.2-all.zip or gradle-8.12.1-bin.zip
        vm = re.search(r'gradle-([\d\.]+)-(bin|all)\.zip', old_url)
        if not vm:
            result['errors'].append('Unable to extract Gradle version from distributionUrl')
            return result
        version = vm.group(1)
        dist_type = vm.group(2)
        try:
            def parse_ver(v: str):
                return [int(x) for x in v.split('.')]
            if parse_ver(version) < parse_ver('6.9.2'):
                version = '6.9.2'
                dist_type = 'all'
                result['enforced_default'] = True
        except Exception:
            pass

        # Build new URL (escaped ':' for properties)
        new_url = f'{artifactory_base}/libs-release/com/baml/plat/gradle/wrapper/gradle-{version}-{dist_type}.zip'
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
        # Ensure networkTimeout present to avoid frequent wrapper download timeouts (temporary change)
        nt_match = re.search(r'(?m)^\s*networkTimeout\s*=\s*(\d+)\s*$', new_content)
        if nt_match is None:
            # Append with a sensible default (10 minutes)
            if not new_content.endswith('\n'):
                new_content += '\n'
            new_content += 'networkTimeout=600000\n'
            result['network_timeout_added'] = True
            result['network_timeout_new'] = 600000
        else:
            prev = int(nt_match.group(1))
            result['network_timeout_prev'] = prev
            if prev < 600000:
                # Increase to default
                new_content = re.sub(r'(?m)^(\s*networkTimeout\s*=\s*)\d+(\s*)$', r"\\1600000\\2", new_content)
                result['network_timeout_changed'] = True
                result['network_timeout_new'] = 600000
        p.write_text(new_content, encoding='utf-8')

        result['success'] = True
        return result

    except Exception as e:
        result['errors'].append(str(e))
        return result
