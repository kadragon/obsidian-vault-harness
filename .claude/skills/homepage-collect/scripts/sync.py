"""One-command collect, verify and render using the maintained implementation."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--env', type=Path)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    config = args.config or scripts.parent / 'references' / 'sites.json'
    output = args.output or args.vault / '12_Projects/2026/통합 홈페이지/10. 사업 진행 정보'
    command = [sys.executable, str(scripts / 'collect.py'), '--vault', str(args.vault), '--output', str(output), '--config', str(config)]
    if args.env:
        command += ['--env', str(args.env)]
    subprocess.run(command, check=True)
    subprocess.run([sys.executable, str(scripts / 'render_notes.py'), '--output', str(output), '--config', str(config)], check=True)
    subprocess.run([sys.executable, str(scripts / 'verify_notes.py'), '--output', str(output), '--vault', str(args.vault)], check=True)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
