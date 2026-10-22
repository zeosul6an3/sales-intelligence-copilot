"""Command-line entry point: `uv run sic serve`."""

import argparse
import shutil
import subprocess
import sys
import threading
import webbrowser

import uvicorn

from sic.config import FRONTEND_DIST, LOCAL_HOSTS, PROJECT_ROOT, get_settings


def build_frontend() -> bool:
    """Build the dashboard with npm. Returns False if that is not possible."""
    npm = shutil.which("npm")  # resolves npm.cmd on Windows
    frontend_dir = PROJECT_ROOT / "frontend"
    if npm is None:
        print("npm was not found. Install Node.js LTS, then run: npm ci --prefix frontend")
        return False
    if not (frontend_dir / "node_modules").is_dir():
        print("Frontend dependencies are missing. Run: npm ci --prefix frontend")
        return False
    print("Building the dashboard (npm run build)...")
    return subprocess.run([npm, "run", "build"], cwd=frontend_dir).returncode == 0


def serve(args: argparse.Namespace) -> int:
    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port

    if host not in LOCAL_HOSTS:
        print(f"Warning: binding to {host} may expose the app to other devices on your network.")

    if not FRONTEND_DIST.is_dir() and not build_frontend():
        print("Starting the API only; the dashboard will not be available until it is built.")

    url = f"http://{'127.0.0.1' if host in LOCAL_HOSTS else host}:{port}"
    print(f"Sales Intelligence Copilot: {url}  (press Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=[url]).start()

    uvicorn.run("sic.main:app", host=host, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sic", description="Sales Intelligence Copilot")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Start the local app")
    serve_parser.add_argument("--host", help="Default: 127.0.0.1 (this computer only)")
    serve_parser.add_argument("--port", type=int, help="Default: 8000")
    serve_parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    serve_parser.set_defaults(func=serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
