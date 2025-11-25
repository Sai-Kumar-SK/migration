#!/usr/bin/env python3
import os
import sys
import tempfile
import shutil
import subprocess
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Optional

from gradle_parser import GradleProjectParser
from settings_template import append_repositories_to_settings
from wrapper_updater import update_gradle_wrapper
import platform
import tempfile
import re

def clone_repo(repo_url: str, work_dir: Path) -> Tuple[bool, str]:
    try:
        if not repo_url.startswith(('git@', 'ssh://')) and 'github.com' in repo_url:
            org = repo_url.split('/')[-2]
            name = repo_url.split('/')[-1].replace('.git', '')
            repo_url = f'git@github.com:{org}/{name}.git'
        r = subprocess.run(['git', 'clone', repo_url, str(work_dir)], capture_output=True, text=True)
        if r.returncode == 0:
            return True, 'cloned'
        return False, r.stderr
    except Exception as e:
        return False, str(e)

def ensure_branch(work_dir: Path, branch_name: str) -> Tuple[bool, str]:
    try:
        create = subprocess.run(['git', 'checkout', '-b', branch_name], cwd=work_dir, capture_output=True, text=True)
        if create.returncode != 0:
            checkout = subprocess.run(['git', 'checkout', branch_name], cwd=work_dir, capture_output=True, text=True)
            if checkout.returncode != 0:
                return False, checkout.stderr
        return True, branch_name
    except Exception as e:
        return False, str(e)

def commit_push(work_dir: Path, message: str) -> Tuple[bool, str]:
    try:
        #subprocess.run(['git', 'config', 'user.name', os.environ.get('GIT_USER', 'Migration Bot')], cwd=work_dir, check=True)
        #subprocess.run(['git', 'config', 'user.email', os.environ.get('GIT_EMAIL', 'migration@bot.com')], cwd=work_dir, check=True)
        subprocess.run(['git', 'add', '.'], cwd=work_dir, check=True)
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=work_dir, capture_output=True, text=True)
        if not status.stdout.strip():
            return True, 'no changes'
        subprocess.run(['git', 'commit', '-m', message], cwd=work_dir, check=True)
        branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=work_dir, capture_output=True, text=True)
        b = branch.stdout.strip() if branch.returncode == 0 else None
        if b:
            subprocess.run(['git', 'push', '-u', 'origin', b], cwd=work_dir, check=True)
        else:
            subprocess.run(['git', 'push'], cwd=work_dir, check=True)
        return True, 'pushed'
    except Exception as e:
        return False, str(e)

def standard_migration(work_dir: Path, artifactory_url: str) -> dict:
    parser = GradleProjectParser(str(work_dir))
    parser.find_all_gradle_files()
    structure = parser.get_project_structure()
    result = {'success': False, 'steps': []}

    # 1. Settings.gradle prepend repositories
    settings = structure.get('settings_gradle')
    if settings:
        ok = append_repositories_to_settings(settings, artifactory_url)
        result['steps'].append({'settings_updated': ok, 'file': settings})

        # Remove any gradle.allprojects { ... } block irrespective of contents
        clean_res = remove_plasma_nexus_block(settings)
        result['steps'].append({'allprojects_block_removed': clean_res.get('removed', False), 'file': settings, 'removed_bytes': clean_res.get('removed_bytes', 0), 'removed_count': clean_res.get('removed_count', 0)})
    else:
        result['steps'].append({'settings_updated': False, 'error': 'settings.gradle not found'})

    # 2. Update gradle-wrapper.properties distributionUrl
    wrapper = structure.get('gradle_wrapper_properties')
    if wrapper:
        wr = update_gradle_wrapper(wrapper, artifactory_base=artifactory_url)
        result['steps'].append({'wrapper_updated': wr['success'], 'old_url': wr['old_url'], 'new_url': wr['new_url'], 'file': wrapper})
    else:
        result['steps'].append({'wrapper_updated': False, 'error': 'gradle-wrapper.properties not found'})

    result['success'] = all(s.get('settings_updated', True) if 'settings_updated' in s else True for s in result['steps']) and \
                        all(s.get('wrapper_updated', True) if 'wrapper_updated' in s else True for s in result['steps'])
    return result

def process_repo(repo_url: str, branch_name: str, commit_message: str, artifactory_url: str, temp_root: Path, java_home_override: Optional[str] = None) -> dict:
    work_dir = temp_root / f"std_mig_{Path(repo_url).stem}"
    out = {'repo': repo_url, 'success': False, 'details': {}}
    ok, msg = clone_repo(repo_url, work_dir)
    if not ok:
        out['details'] = {'error': f'clone failed: {msg}'}
        return out
    b_ok, b_msg = ensure_branch(work_dir, branch_name)
    if not b_ok:
        out['details'] = {'error': f'branch failed: {b_msg}'}
        return out
    # Detect platform
    gp = GradleProjectParser(str(work_dir))
    gp.find_all_gradle_files()
    is_platform = gp.detect_gradle_platform()
    if is_platform:
        out['details'] = {'message': 'gradle_platform detected; awaiting platform flow'}
        return out
    # Standard migration steps
    mig = standard_migration(work_dir, artifactory_url)
    out['details'] = mig
    if mig['success']:
        # Verify dependency resolution before committing
        v_ok, v_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override)
        out['details']['verification'] = {'success': v_ok, 'message': v_msg}
        if not v_ok:
            out['success'] = False
            out['details']['error'] = 'Dependency resolution failed; not committing changes'
            return out
        c_ok, c_msg = commit_push(work_dir, commit_message)
        out['success'] = c_ok
        out['details']['commit'] = c_msg
    return out

def verify_dependency_resolution(work_dir: Path, repo_url: str, java_home_override: Optional[str] = None) -> Tuple[bool, str]:
    """Run Gradle to verify dependencies resolve successfully.

    Prefers Gradle wrapper if present. Falls back to system Gradle.
    """
    try:
        is_windows = platform.system().lower().startswith('win')
        gradlew_bat = work_dir / 'gradlew.bat'
        gradlew_sh = work_dir / 'gradlew'
        if gradlew_sh.exists():
            if is_windows:
                # Prefer running Unix wrapper via bash on Windows when available
                cmd = ['bash', '-lc', './gradlew dependencies --refresh-dependencies --no-daemon']
            else:
                cmd = [str(gradlew_sh), 'dependencies', '--refresh-dependencies', '--no-daemon']
        elif is_windows and gradlew_bat.exists():
            cmd = [str(gradlew_bat), 'dependencies', '--refresh-dependencies', '--no-daemon']
        else:
            cmd = ['gradle', 'dependencies', '--refresh-dependencies', '--no-daemon']

        # Build environment with selected JAVA_HOME
        version = parse_gradle_version_from_wrapper(work_dir)
        java_home = java_home_override if java_home_override else select_java_home_for_gradle_version(version)
        env = os.environ.copy()
        if java_home:
            env['JAVA_HOME'] = java_home
            env['PATH'] = str(Path(java_home) / 'bin') + os.pathsep + env.get('PATH', '')

        proc = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, env=env)

        # Build log file path
        tmp_dir = Path(tempfile.gettempdir())
        # Extract repo name
        repo_name = extract_repo_name(repo_url)
        log_file = tmp_dir / f"dependency-resolution-{repo_name}.log"

        combined = (proc.stdout or '') + "\n" + (proc.stderr or '')
        # Summary of unresolved dependencies
        patterns = ['Could not resolve', 'Could not find', 'Could not get resource', 'UNRESOLVED', 'Failed to download']
        unresolved = []
        seen = set()
        for line in combined.splitlines():
            low = line.lower()
            if any(p.lower() in low for p in patterns):
                key = line.strip()
                if key not in seen:
                    seen.add(key)
                    unresolved.append(key)

        header = f"******************** {repo_name} DEPENDENCY RESOLUTION ***********************\n"
        footer = "**************END*******************\n"
        cmd_line = f"Command: {' '.join(cmd)}\nJAVA_HOME: {java_home or env.get('JAVA_HOME','')}\n"
        summary = ''
        if unresolved:
            summary = "=== Summary of unresolved dependencies ===\n" + "\n".join(f"- {u}" for u in unresolved) + "\n\n"

        try:
            log_file.write_text(header + cmd_line + summary + combined + "\n" + footer, encoding='utf-8')
        except Exception:
            pass

        if proc.returncode == 0:
            return True, f'Dependencies resolved successfully. Log: {log_file}'
        # Collect a concise error message
        err = proc.stderr.strip() or proc.stdout.strip()
        if len(err) > 2000:
            err = err[-2000:]
        return False, (err or 'Gradle dependency resolution failed') + f". Log: {log_file}"
    except FileNotFoundError:
        # Ensure we still write an error log file for visibility
        try:
            tmp_dir = Path(tempfile.gettempdir())
            repo_name = extract_repo_name(repo_url)
            log_file = tmp_dir / f"dependency-resolution-{repo_name}.log"
            header = f"******************** {repo_name} DEPENDENCY RESOLUTION ***********************\n"
            footer = "**************END*******************\n"
            msg = 'Gradle/Gradle wrapper not found in repository'
            log_file.write_text(header + f"JAVA_HOME: {java_home or ''}\n" + msg + "\n" + footer, encoding='utf-8')
            return False, msg + f". Log: {log_file}"
        except Exception:
            return False, 'Gradle/Gradle wrapper not found in repository'
    except Exception as e:
        # Write error log as well
        try:
            tmp_dir = Path(tempfile.gettempdir())
            repo_name = extract_repo_name(repo_url)
            log_file = tmp_dir / f"dependency-resolution-{repo_name}.log"
            header = f"******************** {repo_name} DEPENDENCY RESOLUTION ***********************\n"
            footer = "**************END*******************\n"
            log_file.write_text(header + f"JAVA_HOME: {java_home or ''}\n" + str(e) + "\n" + footer, encoding='utf-8')
            return False, str(e) + f". Log: {log_file}"
        except Exception:
            return False, str(e)

def parse_gradle_version_from_wrapper(work_dir: Path) -> str:
    try:
        props = work_dir / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
        if props.exists():
            content = props.read_text(encoding='utf-8', errors='ignore')
            m = re.search(r'gradle-([\d.]+)-all\.zip', content)
            if m:
                return m.group(1)
        # Fallback: search build files for wrapper { gradleVersion = 'x.y.z' }
        for candidate in ['build.gradle', 'settings.gradle']:
            f = work_dir / candidate
            if f.exists():
                c = f.read_text(encoding='utf-8', errors='ignore')
                m2 = re.search(r"gradleVersion\s*=\s*['\"]([\d.]+)['\"]", c)
                if m2:
                    return m2.group(1)
    except Exception:
        pass
    return ''

def select_java_home_for_gradle_version(version: str) -> str:
    try:
        parts = [int(p) for p in (version.split('.') if version else [])]
        major = parts[0] if parts else 0
        minor = parts[1] if len(parts) > 1 else 0
    except Exception:
        major, minor = 0, 0
    env = os.environ
    def pick_exact(required_major: int) -> str:
        # Prefer exact env var, then validate JAVA_HOME if it matches required major
        order = []
        if required_major == 11:
            order = ['JAVA11_HOME', 'JAVA8_HOME']
        elif required_major in (17, 21):
            order = ['JAVA17_HOME', 'JAVA21_HOME']
        else:
            order = ['JAVA11_HOME', 'JAVA17_HOME', 'JAVA8_HOME', 'JAVA21_HOME']
        for v in order:
            p = env.get(v)
            if p:
                return p
        # Validate existing JAVA_HOME if present
        existing = env.get('JAVA_HOME', '')
        if existing:
            jmaj = detect_java_major(existing)
            if required_major == 11 and (jmaj == 11 or jmaj == 8):
                return existing
            if required_major in (17, 21) and (jmaj >= 17):
                return existing
        return ''
    # Unknown version: prefer 11
    if major == 0:
        return pick_exact(11)
    if major <= 6:
        return pick_exact(11)
    if major == 7:
        if minor >= 3:
            return pick_exact(17)
        return pick_exact(11)
    return pick_exact(17)

def detect_java_major(java_home_path: str) -> int:
    try:
        env = os.environ.copy()
        env['JAVA_HOME'] = java_home_path
        env['PATH'] = str(Path(java_home_path) / 'bin') + os.pathsep + env.get('PATH', '')
        proc = subprocess.run(['java', '-version'], capture_output=True, text=True, env=env)
        out = proc.stderr or proc.stdout or ''
        # Match formats: "1.8.0_", "11.", "17.", "21."
        m = re.search(r'version\s+"(\d+)(?:\.(\d+))?', out)
        if m:
            major = int(m.group(1))
            if major == 1:
                # Java 8 reports as 1.8
                minor = int(m.group(2) or 0)
                return 8 if minor == 8 else major
            return major
    except Exception:
        pass
    return 0

def extract_repo_name(repo_url: str) -> str:
    u = repo_url.strip()
    name = u
    if '@' in u and ':' in u:
        # git@host:org/repo.git
        name = u.split(':', 1)[1].split('/')[-1]
    else:
        parts = u.rstrip('/').split('/')
        name = parts[-1] if parts else u
    if name.endswith('.git'):
        name = name[:-4]
    return name or 'repo'

def remove_plasma_nexus_block(settings_file: str) -> dict:
    """Remove any gradle.allprojects { ... } block from settings.gradle, irrespective of contents.

    Returns dict with keys: removed (bool), removed_bytes (int), removed_count (int), error (optional)
    """
    res = {'removed': False, 'removed_bytes': 0, 'removed_count': 0}
    try:
        p = Path(settings_file)
        if not p.exists():
            return res
        content = p.read_text(encoding='utf-8')
        pattern = re.compile(r'(?is)(?:gradle\.)?allprojects\s*\{')
        removed_any = False
        total_removed = 0
        while True:
            m = pattern.search(content)
            if not m:
                break
            start_idx = m.start()
            # Find matching closing brace from start of this block
            brace_start = content.find('{', start_idx)
            if brace_start == -1:
                break
            depth = 0
            end_idx = None
            for i in range(brace_start, len(content)):
                ch = content[i]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            if end_idx is None:
                break
            # Remove this block
            before = len(content)
            content = content[:start_idx] + content[end_idx+1:]
            after = len(content)
            total_removed += (before - after)
            removed_any = True
            res['removed_count'] += 1
        if removed_any:
            p.write_text(content, encoding='utf-8')
            res['removed'] = True
            res['removed_bytes'] = total_removed
        return res
    except Exception as e:
        res['error'] = str(e)
        return res

def main():
    ap = argparse.ArgumentParser(description='Horizon Standard Gradle Migration (prepend settings + update wrapper)')
    ap.add_argument('--git-urls', nargs='+', help='Git repository URLs (SSH preferred)')
    ap.add_argument('--git-file', help='File with git URLs (one per line)')
    ap.add_argument('--branch-name', default='horizon-migration', help='Branch name to create and use')
    ap.add_argument('--commit-message', default='Migrate settings.gradle and wrapper to Artifactory', help='Commit message')
    ap.add_argument('--artifactory-url', default='https://artifactory.org.com/artifactory', help='Artifactory base URL')
    ap.add_argument('--max-workers', type=int, default=10, help='Parallel workers')
    ap.add_argument('--temp-dir', help='Temporary directory root')
    ap.add_argument('--java-home-override', help='Optional JAVA_HOME override path to use for Gradle invocation')

    args = ap.parse_args()
    repos: List[str] = []
    if args.git_urls:
        repos.extend(args.git_urls)
    if args.git_file:
        p = Path(args.git_file)
        if p.exists():
            repos.extend([l.strip() for l in p.read_text().splitlines() if l.strip()])
    if not repos:
        print('No repositories provided')
        sys.exit(1)

    temp_root = Path(args.temp_dir) if args.temp_dir else Path(tempfile.gettempdir())
    results = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futs = [ex.submit(process_repo, r, args.branch_name, args.commit_message, args.artifactory_url, temp_root, args.java_home_override) for r in repos]
        for f in as_completed(futs):
            results.append(f.result())

    ok_count = sum(1 for r in results if r['success'])
    print(f"Completed. Success: {ok_count}/{len(results)}")
    for r in results:
        print(f"- {r['repo']}: {'OK' if r['success'] else 'FAILED'}")

if __name__ == '__main__':
    main()