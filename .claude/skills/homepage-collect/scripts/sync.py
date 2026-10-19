"""One-command collect, verify and render using the maintained implementation."""
import argparse
from pathlib import Path
import subprocess
import sys
import urllib.error

import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--env', type=Path)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    config = args.config or scripts.parent / 'references' / 'sites.json'
    output = (args.output or args.vault / collect.DEFAULT_OUTPUT).resolve()
    with collect.output_lock(output):
        collect.refresh(root=output, config_path=config, env_path=args.env or args.vault / '.env')
        subprocess.run([sys.executable, str(scripts / 'render_notes.py'), '--output', str(output), '--config', str(config)], check=True)
        subprocess.run([sys.executable, str(scripts / 'verify_notes.py'), '--output', str(output), '--vault', str(args.vault)], check=True)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
    except (collect.CollectionError, urllib.error.URLError, OSError, ValueError, KeyError) as error:
        # Keep collection failures sanitized just as in the standalone collector.
        message = str(error) if isinstance(error, collect.CollectionError) else type(error).__name__
        print('Collection failed: ' + message, file=sys.stderr)
        sys.exit(1)
