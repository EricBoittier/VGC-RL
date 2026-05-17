from __future__ import annotations

import argparse
import json
import mimetypes
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from vgc_rl.replay import list_replay_files


def _viewer_root() -> Path:
    return Path(resources.files("vgc_rl") / "replay_viewer")


class ReplayViewerHandler(SimpleHTTPRequestHandler):
    replay_dir: Path

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/api/replays":
            self._send_json({"replays": [p.name for p in list_replay_files(self.replay_dir)]})

            return

        if self.path.startswith("/api/replays/"):
            name = unquote(self.path.removeprefix("/api/replays/").split("?", 1)[0])

            if not name or "/" in name or "\\" in name or name.startswith("."):
                self.send_error(400, "invalid replay name")

                return

            target = (self.replay_dir / name).resolve()

            if not str(target).startswith(str(self.replay_dir.resolve())) or not target.is_file():
                self.send_error(404, "replay not found")

                return

            with open(target, encoding="utf-8") as f:
                payload = json.load(f)

            self._send_json(payload)

            return

        return super().do_GET()

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def guess_type(self, path: str) -> str:
        ctype = mimetypes.guess_type(path)[0]

        if ctype:
            return ctype

        return "application/octet-stream"


def serve_replay_viewer(*, replay_dir: Path, host: str, port: int) -> None:
    replay_dir = replay_dir.resolve()
    replay_dir.mkdir(parents=True, exist_ok=True)
    viewer = _viewer_root()

    handler_cls = type(
        "BoundReplayViewerHandler",
        (ReplayViewerHandler,),
        {"replay_dir": replay_dir},
    )
    handler = partial(handler_cls, directory=str(viewer))
    server = ThreadingHTTPServer((host, port), handler)

    print(f"Replay viewer · http://{host}:{port}/ · replays → {replay_dir}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the VGC RL browser replay viewer.")
    parser.add_argument("--replay-dir", type=Path, default=Path("replays"), help="Directory with saved replay JSON files")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)

    serve_replay_viewer(replay_dir=args.replay_dir, host=args.host, port=args.port)

    return 0
