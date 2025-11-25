import argparse
import re
import tempfile
from pathlib import Path
from datetime import datetime

def extract_coords(text: str):
    coords = set()
    for m in re.finditer(r'([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)', text):
        coords.add((m.group(1), m.group(2), m.group(3)))
    return coords

def parse_repo_name_from_header(text: str):
    m = re.search(r"\*+\s*(.+?)\s*DEPENDENCY RESOLUTION\s*\*+", text)
    return m.group(1).strip() if m else None

def scan_logs(logs_dir: Path, pattern: str):
    files = sorted(logs_dir.glob(pattern))
    results = []
    for f in files:
        content = f.read_text(encoding='utf-8', errors='ignore')
        repo = parse_repo_name_from_header(content)
        if not repo:
            name = f.stem
            if name.startswith('dependency-resolution-'):
                repo = name[len('dependency-resolution-'):]
            else:
                repo = name
        coords = extract_coords(content)
        if coords:
            results.append({'file': str(f), 'repo': repo, 'coords': coords})
    return results

def load_existing_coords(agg_file: Path):
    if not agg_file.exists():
        return set()
    existing = set()
    content = agg_file.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'^-\s+([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)', content, re.MULTILINE):
        existing.add((m.group(1), m.group(2), m.group(3)))
    return existing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logs-dir', help='Directory containing dependency-resolution-*.log files')
    ap.add_argument('--pattern', default='dependency-resolution-*.log', help='Glob pattern for log files')
    ap.add_argument('--output-file', help='Aggregated output file path')
    args = ap.parse_args()

    logs_dir = Path(args.logs_dir) if args.logs_dir else Path(tempfile.gettempdir())
    output_file = Path(args.output_file) if args.output_file else logs_dir / 'dependency-resolution-aggregated.log'

    results = scan_logs(logs_dir, args.pattern)
    existing = load_existing_coords(output_file)

    new_coords = set()
    coord_to_repos = {}
    for r in results:
        for c in r['coords']:
            if c not in existing:
                new_coords.add(c)
            coord_to_repos.setdefault(c, set()).add(r['repo'])

    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    header = f"===== Aggregation Run {ts} =====\n"
    summary = f"Logs dir: {logs_dir}\nFiles scanned: {len(results)}\nNew unique unresolved dependencies: {len(new_coords)}\n\n"

    lines = [header, summary]
    for g, a, v in sorted(new_coords):
        repos = ', '.join(sorted(coord_to_repos.get((g, a, v), [])))
        lines.append(f"- {g}:{a}:{v} [repos: {repos}]\n")
    lines.append("===== End Aggregation =====\n\n")

    with output_file.open('a', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Appended {len(new_coords)} entries to {output_file}")

if __name__ == '__main__':
    main()