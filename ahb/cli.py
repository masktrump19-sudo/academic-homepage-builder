"""Small local CLI shared with the web wizard."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog='ahb', description='Academic Homepage Builder — local first')
    parser.add_argument('--version', action='version', version='Academic Homepage Builder 0.1.0')
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve', help='Open the local webpage wizard')
    serve.add_argument('--port', type=int, default=8790)
    serve.add_argument('--no-browser', action='store_true')
    build = commands.add_parser('build', help='Build a reviewed site.json project')
    build.add_argument('--project', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('check', help='Check an exported static website')
    check.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            import uvicorn
            from .server import create_app
            if not 1024 <= args.port <= 65535:
                parser.error('Choose a port between 1024 and 65535.')
            print(f'Local wizard: http://127.0.0.1:{args.port} — close this terminal to end the session.')
            if not args.no_browser:
                import threading, webbrowser
                threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
            uvicorn.run(create_app(), host='127.0.0.1', port=args.port, access_log=False, log_level='warning')
        elif args.command == 'build':
            from .exporter import load_project, build_project
            site, assets = load_project(args.project)
            build_project(site, assets, args.output)
            print(f'Built and checked {args.output}. Only reviewed public content was included.')
        else:
            from .exporter import check_directory
            check_directory(args.path)
            print('Static site checks passed.')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Cannot complete this operation: {exc}\n')


if __name__ == '__main__':
    main()
