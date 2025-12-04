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
import logging

from gradle_parser import GradleProjectParser
from settings_template import append_repositories_to_settings, append_repositories_to_settings_g6, get_version_catalog_settings_template
from wrapper_updater import update_gradle_wrapper
from gradle_platform_migrator import GradlePlatformMigrator
import platform
import re

VERBOSE = False
log = logging.getLogger("horizon")

def configure_logger(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='[%(levelname)s] %(message)s')

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
        # Skip checkout if already on the target branch
        cur = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=work_dir, capture_output=True, text=True)
        current = cur.stdout.strip() if cur.returncode == 0 else ''
        if current == branch_name:
            return True, branch_name
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

    # 1. Settings.gradle cleanup then prepend repositories
    settings = structure.get('settings_gradle')
    if settings:
        clean_res = remove_plasma_nexus_block(settings)
        result['steps'].append({'allprojects_block_removed': clean_res.get('removed', False), 'file': settings, 'removed_bytes': clean_res.get('removed_bytes', 0), 'removed_count': clean_res.get('removed_count', 0)})
        log.info("Standard Step 1: settings cleanup - gradle.allprojects block " + ("removed" if clean_res.get('removed') else "not found"))
        if VERBOSE and clean_res.get('removed'):
            log.debug(f"removed_count={clean_res.get('removed_count', 0)} removed_bytes={clean_res.get('removed_bytes', 0)}")

        version = parse_gradle_version_from_wrapper(work_dir)
        use_g6 = False
        try:
            parts = [int(p) for p in (version.split('.') if version else [])]
            major = parts[0] if parts else 0
            use_g6 = (major <= 6) and clean_res.get('removed', False)
        except Exception:
            use_g6 = clean_res.get('removed', False)
        if use_g6:
            ok = append_repositories_to_settings_g6(settings, artifactory_url)
        else:
            ok = append_repositories_to_settings(settings, artifactory_url)
        result['steps'].append({'settings_updated': ok, 'file': settings})
        log.info("Standard Step 1: settings.gradle " + ("updated" if ok else "update skipped or already present"))
        if VERBOSE and ok:
            log.debug(f"settings file: {settings}")
    else:
        result['steps'].append({'settings_updated': False, 'error': 'settings.gradle not found'})
        log.info("Standard Step 2: settings.gradle not found")

    # 2. Update gradle-wrapper.properties distributionUrl
    wrapper = structure.get('gradle_wrapper_properties')
    if wrapper:
        wr = update_gradle_wrapper(wrapper, artifactory_base=artifactory_url)
        result['steps'].append({
            'wrapper_updated': wr['success'],
            'old_url': wr['old_url'],
            'new_url': wr['new_url'],
            'file': wrapper,
            'network_timeout_added': wr.get('network_timeout_added'),
            'network_timeout_changed': wr.get('network_timeout_changed'),
            'network_timeout_prev': wr.get('network_timeout_prev'),
            'network_timeout_new': wr.get('network_timeout_new')
        })
        msg = "Standard Step 2: distributionUrl " + ("updated" if wr.get('success') else "update failed: " + ", ".join(wr.get('errors', [])))
        (log.info if wr.get('success') else log.error)(msg)
        if wr.get('enforced_default'):
            log.info("Standard Step 2: enforcing default Gradle version 6.9.2 for wrapper")
        if VERBOSE and wr.get('success'):
            log.debug(f"old: {wr.get('old_url')} new: {wr.get('new_url')}")
    else:
        result['steps'].append({'wrapper_updated': False, 'error': 'gradle-wrapper.properties not found'})
        log.info("Standard Step 1: distributionUrl update skipped (gradle-wrapper.properties not found)")

    # 3. Remove wrapper block from root build.gradle (only wrapper block)
    root_build = structure.get('root_build_gradle')
    if root_build:
        rem = remove_wrapper_block(root_build)
        result['steps'].append({'root_build_wrapper_removed': rem.get('removed', False), 'file': root_build, 'removed_bytes': rem.get('removed_bytes', 0), 'removed_count': rem.get('removed_count', 0)})
        log.info("Standard Step 3: root build.gradle wrapper " + ("removed" if rem.get('removed') else "not found"))
    else:
        result['steps'].append({'root_build_wrapper_removed': False, 'error': 'root build.gradle not found'})
        log.info("Standard Step 3: root build.gradle not found")

    result['success'] = all(s.get('settings_updated', True) if 'settings_updated' in s else True for s in result['steps']) and \
                        all(s.get('wrapper_updated', True) if 'wrapper_updated' in s else True for s in result['steps']) and \
                        all(s.get('root_build_wrapper_removed', True) if 'root_build_wrapper_removed' in s else True for s in result['steps'])
    return result

def remove_wrapper_block(file_path: str) -> dict:
    res = {'removed': False, 'removed_bytes': 0, 'removed_count': 0}
    try:
        p = Path(file_path)
        if not p.exists():
            return res
        content = p.read_text(encoding='utf-8', errors='ignore')
        pattern = re.compile(r'(?m)^\s*wrapper\s*\{')
        total_removed = 0
        removed_any = False
        pos = 0
        while True:
            m = pattern.search(content, pos)
            if not m:
                break
            start_idx = m.start()
            brace_start = content.find('{', start_idx)
            if brace_start == -1:
                pos = m.end()
                continue
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
                pos = m.end()
                continue
            before = len(content)
            content = content[:start_idx] + content[end_idx+1:]
            after = len(content)
            total_removed += (before - after)
            removed_any = True
            res['removed_count'] += 1
            pos = start_idx
        if removed_any:
            p.write_text(content, encoding='utf-8')
            res['removed'] = True
            res['removed_bytes'] = total_removed
        return res
    except Exception as e:
        res['error'] = str(e)
        return res

def revert_wrapper_network_timeout(work_dir: Path, info: Optional[dict]) -> None:
    try:
        wrapper = work_dir / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
        if not wrapper.exists():
            return
        text = wrapper.read_text(encoding='utf-8', errors='ignore')
        if info and info.get('network_timeout_added'):
            # Remove the line entirely
            new = re.sub(r'(?m)^\s*networkTimeout\s*=\s*\d+\s*\n?', '', text)
            if new != text:
                wrapper.write_text(new, encoding='utf-8')
            return
        if info and info.get('network_timeout_changed'):
            prev = info.get('network_timeout_prev')
            if prev is not None:
                new = re.sub(r'(?m)^(\s*networkTimeout\s*=\s*)\d+(\s*)$', rf"\1{prev}\2", text)
                if new != text:
                    wrapper.write_text(new, encoding='utf-8')
                return
        # Fallback: remove default we may have added
        new = re.sub(r'(?m)^\s*networkTimeout\s*=\s*600000\s*\n?', '', text)
        if new != text:
            wrapper.write_text(new, encoding='utf-8')
    except Exception:
        pass
def process_repo(repo_url: str, branch_name: str, commit_message: str, artifactory_url: str, temp_root: Path, java_home_override: Optional[str] = None, jenkinsfiles: Optional[List[str]] = None, use_cache: bool = True, regen_wrapper: bool = False, verify_only: bool = False) -> dict:
    work_dir = temp_root / f"std_mig_{Path(repo_url).stem}"
    out = {'repo': repo_url, 'success': False, 'details': {}}
    # Rerun support: reuse existing work dir if it already contains a git repo
    if not (work_dir.exists() and (work_dir / '.git').exists()):
        ok, msg = clone_repo(repo_url, work_dir)
        if not ok:
            out['details'] = {'error': f'clone failed: {msg}'}
            log.error(f"Clone failed for {repo_url}: {msg}")
            return out
        log.info("Clone completed")
    else:
        log.info("Rerun detected: using existing work directory (skip clone)")
    b_ok, b_msg = ensure_branch(work_dir, branch_name)
    if not b_ok:
        out['details'] = {'error': f'branch failed: {b_msg}'}
        log.error("Branch setup failed")
        return out
    if regen_wrapper and not verify_only:
        rw = regenerate_wrapper_files(work_dir, java_home_override)
        out.setdefault('details', {})['wrapper_regenerated'] = rw.get('success', False)
        if rw.get('success'):
            log.info("Wrapper regeneration completed")
        else:
            log.error("Wrapper regeneration failed")
    # Detect platform
    gp = GradleProjectParser(str(work_dir))
    gp.find_all_gradle_files()
    is_platform = gp.detect_gradle_platform()
    libs_toml_exists = (work_dir / 'gradle' / 'libs.versions.toml').exists()
    if verify_only:
        # Only run dependency verification and return
        v_ok, v_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
        out['details']['verification'] = {'success': v_ok, 'message': v_msg}
        cleanup_after_verification(work_dir)
        out['success'] = v_ok
        return out
    if is_platform:
        log.info("Flow: gradle_platform")
        pm = GradlePlatformMigrator(str(work_dir), verbose=VERBOSE)
        plat = pm.run_gradle_platform_migration()
        out['details'] = plat
        auto_res = auto_update_jenkinsfiles(work_dir)
        j_list = (jenkinsfiles or ['Jenkinsfile.build.groovy'])
        j_res = update_jenkinsfiles(work_dir, j_list)
        if j_res.get('updated_count', 0) > 0:
            log.info("Gradle Platform: Jenkinsfile(s) updated")
        else:
            log.info("Gradle Platform: Jenkinsfile update skipped")
        if auto_res.get('updated_count', 0) > 0:
            log.info("Gradle Platform: auto Jenkinsfile(s) updated")
        v_ok, v_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
        out['details']['verification'] = {'success': v_ok, 'message': v_msg}
        if not v_ok:
            log.info("Retrying dependency verification with wrapper regeneration")
            rw = regenerate_wrapper_files(work_dir, java_home_override)
            v2_ok, v2_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
            out['details']['verification_retry'] = {'success': v2_ok, 'message': v2_msg}
            cleanup_after_verification(work_dir)
            if not v2_ok:
                out['success'] = False
                out['details']['error'] = 'Dependency resolution failed; not committing changes'
                log.error("Gradle Platform Step 3: dependency verification failed")
                return out
        else:
            cleanup_after_verification(work_dir)
        if VERBOSE:
            log.debug(v_msg)
        log.info("Gradle Platform Step 3: dependency verification passed")
        # Revert temporary networkTimeout change before commit if applied
        plat_wr = plat.get('wrapper_updated') if isinstance(plat, dict) else None
        revert_wrapper_network_timeout(work_dir, plat_wr)
        c_ok, c_msg = commit_push(work_dir, commit_message)
        out['success'] = c_ok
        out['details']['commit'] = c_msg
        return out
    elif libs_toml_exists:
        # Version catalog present but not plasma; run catalog-only adjustments
        log.info("Flow: version_catalog_non_plasma")
        cat = catalog_non_plasma_migration(work_dir)
        out['details'] = cat
        if cat.get('success'):
            auto_res = auto_update_jenkinsfiles(work_dir)
            j_list = (jenkinsfiles or ['Jenkinsfile.build.groovy'])
            j_res = update_jenkinsfiles(work_dir, j_list)
            if j_res.get('updated_count', 0) > 0:
                log.info("Version Catalog: Jenkinsfile(s) updated")
            else:
                log.info("Version Catalog: Jenkinsfile update skipped")
            if auto_res.get('updated_count', 0) > 0:
                log.info("Version Catalog: auto Jenkinsfile(s) updated")
            v_ok, v_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
            out['details']['verification'] = {'success': v_ok, 'message': v_msg}
            if not v_ok:
                log.info("Retrying dependency verification with wrapper regeneration")
                rw = regenerate_wrapper_files(work_dir, java_home_override)
                v2_ok, v2_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
                out['details']['verification_retry'] = {'success': v2_ok, 'message': v2_msg}
                cleanup_after_verification(work_dir)
                if not v2_ok:
                    out['success'] = False
                    out['details']['error'] = 'Dependency resolution failed; not committing changes'
                    log.error("Version Catalog Step 3: dependency verification failed")
                    return out
            else:
                cleanup_after_verification(work_dir)
            if VERBOSE:
                log.debug(v_msg)
            log.info("Version Catalog Step 3: dependency verification passed")
            # Revert temporary networkTimeout change before commit if applied
            try:
                cat_wr = None
                steps = out.get('details', {}).get('steps', []) if isinstance(out.get('details'), dict) else []
                for s in steps:
                    if 'wrapper_updated' in s and 'file' in s:
                        cat_wr = {
                            'network_timeout_added': s.get('network_timeout_added'),
                            'network_timeout_changed': s.get('network_timeout_changed'),
                            'network_timeout_prev': s.get('network_timeout_prev'),
                            'network_timeout_new': s.get('network_timeout_new')
                        }
                        break
                revert_wrapper_network_timeout(work_dir, cat_wr)
            except Exception:
                revert_wrapper_network_timeout(work_dir, None)
            c_ok, c_msg = commit_push(work_dir, commit_message)
            out['success'] = c_ok
            out['details']['commit'] = c_msg
        return out
    # Standard migration steps
    log.info("Flow: standard")
    mig = standard_migration(work_dir, artifactory_url)
    out['details'] = mig
    if mig['success']:
        # Update Jenkinsfile(s) before Gradle invocation
        auto_res = auto_update_jenkinsfiles(work_dir)
        j_list = (jenkinsfiles or ['Jenkinsfile.build.groovy'])
        j_res = update_jenkinsfiles(work_dir, j_list)
        if j_res.get('updated_count', 0) > 0:
            log.info("Standard Step 3: Jenkinsfile(s) updated")
        else:
            log.info("Standard Step 3: Jenkinsfile update skipped")
        if auto_res.get('updated_count', 0) > 0:
            log.info("Standard Step 3: auto Jenkinsfile(s) updated")
        # Verify dependency resolution before committing
        v_ok, v_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
        out['details']['verification'] = {'success': v_ok, 'message': v_msg}
        if not v_ok:
            log.info("Retrying dependency verification with wrapper regeneration")
            rw = regenerate_wrapper_files(work_dir, java_home_override)
            v2_ok, v2_msg = verify_dependency_resolution(work_dir, repo_url, java_home_override, use_cache)
            out['details']['verification_retry'] = {'success': v2_ok, 'message': v2_msg}
            cleanup_after_verification(work_dir)
            if not v2_ok:
                out['success'] = False
                out['details']['error'] = 'Dependency resolution failed; not committing changes'
            log.error("Standard Step 4: dependency verification failed")
            return out
        else:
            cleanup_after_verification(work_dir)
        if VERBOSE:
            log.debug(v_msg)
        log.info("Standard Step 4: dependency verification passed")
        # Revert temporary networkTimeout change before commit if applied
        try:
            wr_info = None
            for s in out.get('details', {}).get('steps', []):
                if 'wrapper_updated' in s and 'file' in s:
                    wr_info = {
                        'network_timeout_added': s.get('network_timeout_added'),
                        'network_timeout_changed': s.get('network_timeout_changed'),
                        'network_timeout_prev': s.get('network_timeout_prev'),
                        'network_timeout_new': s.get('network_timeout_new')
                    }
                    break
            revert_wrapper_network_timeout(work_dir, wr_info)
        except Exception:
            revert_wrapper_network_timeout(work_dir, None)
        c_ok, c_msg = commit_push(work_dir, commit_message)
        out['success'] = c_ok
        out['details']['commit'] = c_msg
        log.info("Standard Step 5: commit " + ("pushed" if c_ok else c_msg))
    return out

def catalog_non_plasma_migration(work_dir: Path) -> dict:
    """Perform minimal changes for repos with libs.versions.toml but no plasmaGradlePlugins."""
    result = {'success': False, 'steps': [], 'errors': []}
    try:
        # Update wrapper
        wrapper_path = work_dir / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
        if wrapper_path.exists():
            wr = update_gradle_wrapper(str(wrapper_path))
            result['steps'].append({
                'wrapper_updated': wr.get('success', False),
                'old_url': wr.get('old_url'),
                'new_url': wr.get('new_url'),
                'file': str(wrapper_path),
                'network_timeout_added': wr.get('network_timeout_added'),
                'network_timeout_changed': wr.get('network_timeout_changed'),
                'network_timeout_prev': wr.get('network_timeout_prev'),
                'network_timeout_new': wr.get('network_timeout_new')
            })
            msg = "Version Catalog Step 1: distributionUrl " + ("updated" if wr.get('success') else "update failed: " + ", ".join(wr.get('errors', [])))
            (log.info if wr.get('success') else log.error)(msg)
        else:
            result['steps'].append({'wrapper_updated': False, 'error': 'gradle-wrapper.properties not found'})
            log.info("Version Catalog Step 1: distributionUrl update skipped (gradle-wrapper.properties not found)")
        
        # Replace buildSrc/settings.gradle with version catalog template if provided
        tpl = get_version_catalog_settings_template()
        buildsrc_settings = work_dir / 'buildSrc' / 'settings.gradle'
        if tpl and tpl.strip():
            buildsrc_settings.parent.mkdir(parents=True, exist_ok=True)
            buildsrc_settings.write_text(tpl, encoding='utf-8')
            result['steps'].append({'buildsrc_settings_replaced': True, 'file': str(buildsrc_settings)})
            log.info("Version Catalog Step 2: buildSrc/settings.gradle replaced")
        else:
            result['steps'].append({'buildsrc_settings_replaced': False, 'message': 'VERSION_CATALOG_SETTINGS_GRADLE_TEMPLATE empty; skipped'})
            log.info("Version Catalog Step 2: buildSrc/settings.gradle replacement skipped (template empty)")
        
        # Clean root settings.gradle to be minimal
        pm = GradlePlatformMigrator(str(work_dir))
        clean = pm.clean_root_settings_gradle()
        result['steps'].append({'root_settings_cleaned': clean.get('valid', False), 'file': str(work_dir / 'settings.gradle')})
        log.info("Version Catalog Step 2: root settings cleanup " + ("applied" if clean.get('valid') else "skipped"))
        
        result['success'] = all(
            s.get('wrapper_updated', True) if 'wrapper_updated' in s else True for s in result['steps']
        ) and all(
            s.get('root_settings_cleaned', True) if 'root_settings_cleaned' in s else True for s in result['steps']
        )
        return result
    except Exception as e:
        result['errors'].append(str(e))
        return result

def verify_dependency_resolution(work_dir: Path, repo_url: str, java_home_override: Optional[str] = None, use_cache: bool = True) -> Tuple[bool, str]:
    """Run Gradle to verify dependencies resolve successfully.

    Prefers Gradle wrapper if present. Falls back to system Gradle.
    """
    java_home: Optional[str] = None
    try:
        is_windows = platform.system().lower().startswith('win')
        gradlew_bat = work_dir / 'gradlew.bat'
        gradlew_sh = work_dir / 'gradlew'
        init_path = work_dir / 'initResolveAll.gradle'
        init_script = build_init_script()
        init_path.write_text(init_script, encoding='utf-8')
        cache_dir = None
        if use_cache:
            cache_dir = work_dir / '.gradle-user-home'
            cache_dir.mkdir(parents=True, exist_ok=True)
            git_exclude = work_dir / '.git' / 'info' / 'exclude'
            try:
                if git_exclude.exists():
                    ex_text = git_exclude.read_text(encoding='utf-8', errors='ignore')
                    if '.gradle-user-home/' not in ex_text:
                        git_exclude.write_text(ex_text + '\n.gradle-user-home/\n', encoding='utf-8')
            except Exception:
                pass
            # Ensure wrapper credentials available in per-repo user home
            try:
                src_p = Path.home() / '.gradle' / 'gradle.properties'
                user_val = ''
                pass_val = ''
                if src_p.exists():
                    t = src_p.read_text(encoding='utf-8', errors='ignore')
                    m1 = re.search(r'(?m)^\s*systemProp\.gradle\.wrapperUser\s*=\s*(.+)\s*$', t)
                    m2 = re.search(r'(?m)^\s*systemProp\.gradle\.wrapperPassword\s*=\s*(.+)\s*$', t)
                    if m1:
                        user_val = m1.group(1).strip()
                    if m2:
                        pass_val = m2.group(1).strip()
                    if not user_val:
                        m1b = re.search(r'(?m)^\s*gradle\.wrapperUser\s*=\s*(.+)\s*$', t)
                        if m1b:
                            user_val = m1b.group(1).strip()
                    if not pass_val:
                        m2b = re.search(r'(?m)^\s*gradle\.wrapperPassword\s*=\s*(.+)\s*$', t)
                        if m2b:
                            pass_val = m2b.group(1).strip()
                    if not user_val:
                        m1c = re.search(r'(?m)^\s*artifactory_user\s*=\s*(.+)\s*$', t)
                        if m1c:
                            user_val = m1c.group(1).strip()
                    if not pass_val:
                        m2c = re.search(r'(?m)^\s*artifactory_password\s*=\s*(.+)\s*$', t)
                        if m2c:
                            pass_val = m2c.group(1).strip()
                dest_props = cache_dir / 'gradle.properties'
                lines = []
                if user_val:
                    lines.append(f"systemProp.gradle.wrapperUser={user_val}")
                if pass_val:
                    lines.append(f"systemProp.gradle.wrapperPassword={pass_val}")
                if lines:
                    dest_props.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            except Exception:
                pass
        
        if gradlew_sh.exists():
            if is_windows:
                if use_cache and cache_dir:
                    cmd = ['bash', '-lc', f'./gradlew -g "{cache_dir}" -I "{init_path}" resolveAllDeps --refresh-dependencies --no-configuration-cache --no-daemon --console=plain']
                else:
                    cmd = ['bash', '-lc', f'./gradlew -I "{init_path}" resolveAllDeps --refresh-dependencies --no-configuration-cache --no-daemon --console=plain']
            else:
                if use_cache and cache_dir:
                    cmd = [str(gradlew_sh), '-g', str(cache_dir), '-I', str(init_path), 'resolveAllDeps', '--refresh-dependencies', '--no-configuration-cache', '--no-daemon', '--console=plain']
                else:
                    cmd = [str(gradlew_sh), '-I', str(init_path), 'resolveAllDeps', '--refresh-dependencies', '--no-configuration-cache', '--no-daemon', '--console=plain']
        elif is_windows and gradlew_bat.exists():
            if use_cache and cache_dir:
                cmd = [str(gradlew_bat), '-g', str(cache_dir), '-I', str(init_path), 'resolveAllDeps', '--refresh-dependencies', '--no-configuration-cache', '--no-daemon', '--console=plain']
            else:
                cmd = [str(gradlew_bat), '-I', str(init_path), 'resolveAllDeps', '--refresh-dependencies', '--no-configuration-cache', '--no-daemon', '--console=plain']
        else:
            if use_cache and cache_dir:
                cmd = ['gradle', '-g', str(cache_dir), '-I', str(init_path), 'resolveAllDeps', '--refresh-dependencies', '--no-configuration-cache', '--no-daemon', '--console=plain']
            else:
                cmd = ['gradle', '-I', str(init_path), 'resolveAllDeps', '--refresh-dependencies', '--no-configuration-cache', '--no-daemon', '--console=plain']

        # Build environment with selected JAVA_HOME
        version = parse_gradle_version_from_wrapper(work_dir)
        java_home = java_home_override if java_home_override else select_java_home_for_gradle_version(version)
        env = os.environ.copy()
        # Keep OS home for any default resolution; rely on -g to set Gradle user home
        user_home = Path.home()
        env['HOME'] = str(user_home)
        if platform.system().lower().startswith('win'):
            env['USERPROFILE'] = str(user_home)
        if use_cache and cache_dir:
            env['GRADLE_USER_HOME'] = str(cache_dir)
        if java_home:
            env['JAVA_HOME'] = java_home
            env['PATH'] = str(Path(java_home) / 'bin') + os.pathsep + env.get('PATH', '')

        proc = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, env=env)

        # Build log file path
        tmp_dir = Path(tempfile.gettempdir())
        repo_name = extract_repo_name(repo_url)
        spk = extract_spk(repo_url)
        log_file = tmp_dir / f"dependency-resolution-{spk}-{repo_name}.log"

        combined = (proc.stdout or '') + "\n" + (proc.stderr or '')
        # Summary of unresolved dependencies
        patterns = ['UNRESOLVED |', 'Could not resolve', 'Could not find', 'Could not get resource', 'Failed to download']
        unresolved = []
        seen = set()
        for line in combined.splitlines():
            low = line.lower()
            if any(p.lower() in low for p in patterns):
                key = line.strip()
                if key not in seen:
                    seen.add(key)
                    unresolved.append(key)

        header = f"******************** {spk}/{repo_name} DEPENDENCY RESOLUTION ***********************\n"
        footer = "**************END*******************\n"
        raw_cmd = ' '.join(cmd)
        gradle_user_home_display = (str(cache_dir) if (use_cache and cache_dir) else env.get('GRADLE_USER_HOME', str(Path.home() / '.gradle')))
        cmd_line = f"Command: {raw_cmd}\nJAVA_HOME: {java_home or env.get('JAVA_HOME','')}\nGRADLE_USER_HOME: {gradle_user_home_display}\n"
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
            spk = extract_spk(repo_url)
            log_file = tmp_dir / f"dependency-resolution-{spk}-{repo_name}.log"
            header = f"******************** {spk}/{repo_name} DEPENDENCY RESOLUTION ***********************\n"
            footer = "**************END*******************\n"
            msg = 'Gradle/Gradle wrapper not found in repository'
            gradle_user_home_display = env.get('GRADLE_USER_HOME', str(Path.home() / '.gradle'))
            log_file.write_text(header + f"JAVA_HOME: {java_home or ''}\nGRADLE_USER_HOME: {gradle_user_home_display}\n" + msg + "\n" + footer, encoding='utf-8')
            return False, msg + f". Log: {log_file}"
        except Exception:
            return False, 'Gradle/Gradle wrapper not found in repository'
    except Exception as e:
        # Write error log as well
        try:
            tmp_dir = Path(tempfile.gettempdir())
            repo_name = extract_repo_name(repo_url)
            spk = extract_spk(repo_url)
            log_file = tmp_dir / f"dependency-resolution-{spk}-{repo_name}.log"
            header = f"******************** {spk}/{repo_name} DEPENDENCY RESOLUTION ***********************\n"
            footer = "**************END*******************\n"
            gradle_user_home_display = env.get('GRADLE_USER_HOME', str(Path.home() / '.gradle'))
            log_file.write_text(header + f"JAVA_HOME: {java_home or ''}\nGRADLE_USER_HOME: {gradle_user_home_display}\n" + str(e) + "\n" + footer, encoding='utf-8')
            return False, str(e) + f". Log: {log_file}"
        except Exception:
            return False, str(e)

def regenerate_wrapper_files(work_dir: Path, java_home_override: Optional[str] = None) -> dict:
    try:
        props = work_dir / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
        if not props.exists():
            return {'success': False, 'error': 'gradle-wrapper.properties not found'}
        t = props.read_text(encoding='utf-8', errors='ignore')
        m = re.search(r'(?m)^\s*distributionUrl\s*=\s*(.+)\s*$', t)
        if not m:
            return {'success': False, 'error': 'distributionUrl not found'}
        dist_url = m.group(1).strip().replace('\\:', ':')
        is_windows = platform.system().lower().startswith('win')
        gradlew_bat = work_dir / 'gradlew.bat'
        gradlew_sh = work_dir / 'gradlew'
        cmd = []
        if gradlew_sh.exists() and not is_windows:
            cmd = [str(gradlew_sh), 'wrapper', '--gradle-distribution-url', dist_url, '--no-daemon']
        elif is_windows and gradlew_bat.exists():
            cmd = [str(gradlew_bat), 'wrapper', '--gradle-distribution-url', dist_url, '--no-daemon']
        else:
            cmd = ['gradle', 'wrapper', '--gradle-distribution-url', dist_url, '--no-daemon']
        env = os.environ.copy()
        version = parse_gradle_version_from_wrapper(work_dir)
        java_home = java_home_override if java_home_override else select_java_home_for_gradle_version(version)
        if java_home:
            env['JAVA_HOME'] = java_home
            env['PATH'] = str(Path(java_home) / 'bin') + os.pathsep + env.get('PATH', '')
        user_home = Path.home()
        env['HOME'] = str(user_home)
        if platform.system().lower().startswith('win'):
            env['USERPROFILE'] = str(user_home)
        p = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, env=env)
        if p.returncode == 0:
            return {'success': True}
        err = p.stderr.strip() or p.stdout.strip()
        return {'success': False, 'error': err}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def build_init_script() -> str:
    return (
        "initscript { }\n"+
        "gradle.beforeProject { p -> }\n"+
        "allprojects {\n"+
        "    tasks.register('resolveAllDeps') {\n"+
        "        doLast {\n"+
        "            def prj = project.path\n"+
        "            def unresolved = []\n"+
        "            def collectUnresolved = { rr ->\n"+
        "                try {\n"+
        "                    rr.root.dependencies.each { d ->\n"+
        "                        if (d instanceof org.gradle.api.artifacts.result.UnresolvedDependencyResult) {\n"+
        "                            def sel = d.attempted\n"+
        "                            def cause = d.failure?.message ?: ''\n"+
        "                            println \"UNRESOLVED | ${prj} | UNKNOWN | ${sel.group}:${sel.name}:${sel.version} | ${cause}\"\n"+
        "                        }\n"+
        "                    }\n"+
        "                } catch (Throwable t) { }\n"+
        "            }\n"+
        "            configurations.findAll { it.canBeResolved }.each { cfg ->\n"+
        "                try {\n"+
        "                    def rr = cfg.incoming.resolutionResult\n"+
        "                    collectUnresolved(rr)\n"+
        "                } catch (Throwable t) {\n"+
        "                    println \"UNRESOLVED | ${prj} | ${cfg.name} | UNKNOWN | ${t.message}\"\n"+
        "                }\n"+
        "                try { cfg.resolve() } catch (Throwable t) {\n"+
        "                    println \"UNRESOLVED | ${prj} | ${cfg.name} | UNKNOWN | ${t.message}\"\n"+
        "                }\n"+
        "            }\n"+
        "            if (project.buildscript?.configurations) {\n"+
        "                project.buildscript.configurations.findAll { it.canBeResolved }.each { bc ->\n"+
        "                    try {\n"+
        "                        def rr2 = bc.incoming.resolutionResult\n"+
        "                        collectUnresolved(rr2)\n"+
        "                    } catch (Throwable t) {\n"+
        "                        println \"UNRESOLVED | ${prj} | buildscript:${bc.name} | UNKNOWN | ${t.message}\"\n"+
        "                    }\n"+
        "                    try { bc.resolve() } catch (Throwable t) {\n"+
        "                        println \"UNRESOLVED | ${prj} | buildscript:${bc.name} | UNKNOWN | ${t.message}\"\n"+
        "                    }\n"+
        "                }\n"+
        "            }\n"+
        "        }\n"+
        "    }\n"+
        "}\n"
    )

def cleanup_after_verification(work_dir: Path) -> None:
    try:
        init_path = work_dir / 'initResolveAll.gradle'
        if init_path.exists():
            try:
                init_path.unlink()
            except Exception:
                pass
        user_home_dir = work_dir / '.gradle-user-home'
        if user_home_dir.exists():
            try:
                shutil.rmtree(user_home_dir, ignore_errors=True)
            except Exception:
                pass
    except Exception:
        pass

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

def extract_spk(repo_url: str) -> str:
    u = repo_url.strip()
    try:
        if '@' in u and ':' in u:
            # git@host:spk/repo.git
            path = u.split(':', 1)[1]
            parts = path.strip('/').split('/')
            return parts[-2] if len(parts) >= 2 else 'org'
        elif '://' in u:
            # ssh://git@host/spk/repo.git or https://host/spk/repo.git
            path = u.split('://', 1)[1]
            # strip leading host and possible user@
            if '/' in path:
                path = path.split('/', 1)[1]
            parts = path.strip('/').split('/')
            return parts[0] if parts else 'org'
        else:
            parts = u.strip('/').split('/')
            return parts[-2] if len(parts) >= 2 else 'org'
    except Exception:
        return 'org'

def update_jenkinsfile_buildgroovy(work_dir: Path) -> dict:
    return update_jenkinsfiles(work_dir, ['Jenkinsfile.build.groovy'])

def update_jenkinsfiles(work_dir: Path, files: List[str]) -> dict:
    res = {'updated_count': 0, 'updated_files': [], 'skipped_files': []}
    try:
        for rel in files:
            p = work_dir / rel
            if not p.exists():
                res['skipped_files'].append(str(p))
                continue
            text = p.read_text(encoding='utf-8', errors='ignore')
            if 'env.GRADLE_PARAMS' in text:
                res['skipped_files'].append(str(p))
                continue
            lines = text.splitlines()
            idx = None
            for i, line in enumerate(lines):
                if '@Library' in line:
                    idx = i
                    break
            insert_line = "env.GRADLE_PARAMS = \" -Dgradle.wrapperUser=\\${ORG_GRADLE_PROJECT_artifactory_user} -Dgradle.wrapperPassword=\\${ORG_GRADLE_PROJECT_artifactory_password}\""
            if idx is not None:
                lines.insert(idx + 1, "")
                lines.insert(idx + 2, insert_line)
            else:
                lines.insert(0, insert_line)
            p.write_text('\n'.join(lines), encoding='utf-8')
            res['updated_count'] += 1
            res['updated_files'].append(str(p))
        return res
    except Exception as e:
        res['error'] = str(e)
        return res
        
def auto_update_jenkinsfiles(work_dir: Path) -> dict:
    res = {'updated_count': 0, 'updated_files': [], 'skipped_files': [], 'candidates': []}
    try:
        root_candidates = list(Path(work_dir).glob('Jenkinsfile.*.groovy'))
        jobs_dir = Path(work_dir) / 'jobs'
        jobs_candidates = list(jobs_dir.glob('Jenkinsfile.*.groovy')) if jobs_dir.exists() else []
        targets = root_candidates + jobs_candidates
        res['candidates'] = [str(p) for p in targets]
        if not targets:
            return res
        to_update: List[str] = []
        for p in targets:
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
                if ('stageGradlew' in text) or ('gradlew' in text):
                    to_update.append(str(p.relative_to(work_dir)))
                else:
                    res['skipped_files'].append(str(p))
            except Exception:
                res['skipped_files'].append(str(p))
        if to_update:
            upd = update_jenkinsfiles(work_dir, to_update)
            res['updated_count'] += upd.get('updated_count', 0)
            res['updated_files'].extend(upd.get('updated_files', []))
            res['skipped_files'].extend(upd.get('skipped_files', []))
        return res
    except Exception as e:
        res['error'] = str(e)
        return res

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
    ap.add_argument('--jenkinsfiles', nargs='+', default=['Jenkinsfile.build.groovy'], help='Relative Jenkinsfile paths to update with env.GRADLE_PARAMS')
    ap.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    ap.add_argument('--regen-wrapper', action='store_true', help='Regenerate gradle/wrapper/gradle-wrapper.jar before migration')
    ap.add_argument('--verify-only', action='store_true', help='Only run dependency verification (retry gradlew) without making changes')

    args = ap.parse_args()
    global VERBOSE
    VERBOSE = bool(args.verbose)
    configure_logger(VERBOSE)
    repos: List[str] = []
    if args.git_urls:
        repos.extend(args.git_urls)
    if args.git_file:
        p = Path(args.git_file)
        if p.exists():
            repos.extend([l.strip() for l in p.read_text().splitlines() if l.strip()])
    if not repos:
        log.error('No repositories provided')
        sys.exit(1)

    temp_root = Path(args.temp_dir) if args.temp_dir else Path(tempfile.gettempdir())
    results = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        use_cache = bool(args.git_file)
        futs = [ex.submit(process_repo, r, args.branch_name, args.commit_message, args.artifactory_url, temp_root, args.java_home_override, args.jenkinsfiles, use_cache, bool(args.regen_wrapper), bool(args.verify_only)) for r in repos]
        for f in as_completed(futs):
            results.append(f.result())

    ok_count = sum(1 for r in results if r['success'])
    log.info(f"Completed. Success: {ok_count}/{len(results)}")
    for r in results:
        log.info(f"- {r['repo']}: {'OK' if r['success'] else 'FAILED'}")

if __name__ == '__main__':
    main()