# SPDX-License-Identifier: MIT
"""Serve the built explorer on loopback; the repository and credentials are not served."""

from __future__ import annotations

import argparse
import errno
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from project import LOCAL_PREVIEW, ROOT

DEFAULT_PORT = 8765


class PreviewRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def create_server(root: Path, port: int | None = None) -> ThreadingHTTPServer:
    """Use the preferred port, falling back only when that default is occupied.

    An explicit port is respected; 0 asks the OS to select a free port.
    """
    handler = partial(PreviewRequestHandler, directory=str(root))
    try:
        return ThreadingHTTPServer(
            ("127.0.0.1", DEFAULT_PORT if port is None else port), handler
        )
    except OSError as error:
        if port is not None or error.errno != errno.EADDRINUSE:
            raise
        return ThreadingHTTPServer(("127.0.0.1", 0), handler)


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Port must be an integer from 0 to 65535."
        ) from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be from 0 to 65535.")
    return port


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=port_number,
        help=f"Use a specific port (default: {DEFAULT_PORT}, or a free port if busy). Use 0 for automatic selection.",
    )
    parser.add_argument(
        "--local-media",
        action="store_true",
        help="Serve the private .local/preview build",
    )
    options = parser.parse_args()
    root = LOCAL_PREVIEW if options.local_media else ROOT / "dist"
    if not (root / "index.html").is_file():
        build_option = " -- --local-media" if options.local_media else ""
        raise SystemExit(f"Run npm run build{build_option} first.")
    try:
        server = create_server(root, options.port)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            parser.exit(
                1,
                f"Port {options.port} is already in use. Try --port 0 or another port.\n",
            )
        raise
    print(
        f"Clock Explorer: http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
