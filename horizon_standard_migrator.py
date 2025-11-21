#!/usr/bin/env python3
import os
import sys
import tempfile
import shutil
import subprocess
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from gradle_parser import GradleProjectParser
from settings_template import append_repositories_to_settings
from wrapper_updater import update_gradle_wrapper
import platform

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
        subprocess.run(['git', 'config', 'user.name', os.environ.get('GIT_USER', 'Migration Bot')], cwd=work_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', os.environ.get('GIT_EMAIL', 'migration@bot.com')], cwd=work_dir, check=True)
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

def process_repo(repo_url: str, branch_name: str, commit_message: str, artifactory_url: str, temp_root: Path) -> dict:
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
        v_ok, v_msg = verify_dependency_resolution(work_dir)
        out['details']['verification'] = {'success': v_ok, 'message': v_msg}
        if not v_ok:
            out['success'] = False
            out['details']['error'] = 'Dependency resolution failed; not committing changes'
            return out
        c_ok, c_msg = commit_push(work_dir, commit_message)
        out['success'] = c_ok
        out['details']['commit'] = c_msg
    return out

def verify_dependency_resolution(work_dir: Path) -> Tuple[bool, str]:
    """Run Gradle to verify dependencies resolve successfully.

    Prefers Gradle wrapper if present. Falls back to system Gradle.
    """
    try:
        is_windows = platform.system().lower().startswith('win')
        gradlew_bat = work_dir / 'gradlew.bat'
        gradlew_sh = work_dir / 'gradlew'
        if is_windows and gradlew_bat.exists():
            cmd = [str(gradlew_bat), 'dependencies', '--refresh-dependencies', '--no-daemon']
        elif (not is_windows) and gradlew_sh.exists():
            cmd = [str(gradlew_sh), 'dependencies', '--refresh-dependencies', '--no-daemon']
        else:
            # Fallback to system gradle
            cmd = ['gradle', 'dependencies', '--refresh-dependencies', '--no-daemon']

        proc = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
        if proc.returncode == 0:
            return True, 'Dependencies resolved successfully'
        # Collect a concise error message
        err = proc.stderr.strip() or proc.stdout.strip()
        # Limit message size
        if len(err) > 2000:
            err = err[-2000:]
        return False, err or 'Gradle dependency resolution failed'
    except FileNotFoundError:
        return False, 'Gradle/Gradle wrapper not found in repository'
    except Exception as e:
        return False, str(e)

def main():
    ap = argparse.ArgumentParser(description='Horizon Standard Gradle Migration (prepend settings + update wrapper)')
    ap.add_argument('--git-urls', nargs='+', help='Git repository URLs (SSH preferred)')
    ap.add_argument('--git-file', help='File with git URLs (one per line)')
    ap.add_argument('--branch-name', default='horizon-migration', help='Branch name to create and use')
    ap.add_argument('--commit-message', default='Migrate settings.gradle and wrapper to Artifactory', help='Commit message')
    ap.add_argument('--artifactory-url', default='https://artifactory.org.com/artifactory', help='Artifactory base URL')
    ap.add_argument('--max-workers', type=int, default=10, help='Parallel workers')
    ap.add_argument('--temp-dir', help='Temporary directory root')

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
        futs = [ex.submit(process_repo, r, args.branch_name, args.commit_message, args.artifactory_url, temp_root) for r in repos]
        for f in as_completed(futs):
            results.append(f.result())

    ok_count = sum(1 for r in results if r['success'])
    print(f"Completed. Success: {ok_count}/{len(results)}")
    for r in results:
        print(f"- {r['repo']}: {'OK' if r['success'] else 'FAILED'}")

if __name__ == '__main__':
    main()