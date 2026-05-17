from __future__ import annotations

import argparse
import json
import mimetypes
import time
from functools import lru_cache, partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.request import Request, urlopen

from vgc_rl.replay import list_replay_files, write_replay
from vgc_rl.viewer_simulate import (
    apply_vs_greedy,
    default_viewer_team_keys,
    list_policy_zips,
    list_teams_for_viewer,
    resolve_policy_path,
    simulate_ai_replay,
    viewer_simulate_defaults,
)


def _viewer_root() -> Path:
    return Path(resources.files("vgc_rl") / "replay_viewer")


@lru_cache(maxsize=1)
def _sprite_lookup() -> tuple[dict[str, str], dict[str, str]]:
    raw = json.loads((_viewer_root() / "champions_sprite_map.json").read_text(encoding="utf-8"))

    if isinstance(raw.get("bySpecies"), dict):
        return dict(raw["bySpecies"]), dict(raw.get("byFile") or {})

    return dict(raw), {}


class ReplayViewerHandler(SimpleHTTPRequestHandler):
    replay_dir: Path
    policy_dir: Path
    default_alpha_policy: Path | None
    default_beta_policy: Path | None
    fake_oracle: bool
    oracle_url: str | None
    game: str
    meta_pool_policies: bool

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/replays":
            self._send_json({"replays": [p.name for p in list_replay_files(self.replay_dir)]})

            return

        if self.path == "/api/teams":
            self._send_json({"teams": list_teams_for_viewer(six_mon_only=True)})

            return

        if self.path in ("/api/policies", "/api/config"):
            zips = list_policy_zips(self.policy_dir)
            alpha_default, beta_default = default_viewer_team_keys()
            sim_defaults = viewer_simulate_defaults()
            sim_defaults["team_alpha_key"] = alpha_default
            sim_defaults["team_beta_key"] = beta_default
            sim_defaults["game"] = self.game
            sim_defaults["meta_pool_policies"] = self.meta_pool_policies
            sim_defaults["live_oracle"] = not self.fake_oracle
            sim_defaults["alpha_policy"] = (
                self.default_alpha_policy.name if self.default_alpha_policy and self.default_alpha_policy.is_file() else None
            )
            sim_defaults["beta_policy"] = (
                self.default_beta_policy.name if self.default_beta_policy and self.default_beta_policy.is_file() else None
            )
            self._send_json(
                {
                    "policies": zips,
                    "policy_dir": str(self.policy_dir.resolve()),
                    "replay_dir": str(self.replay_dir.resolve()),
                    "defaults": sim_defaults,
                    "options": {
                        "games": ["champions", "sv"],
                        "vs_greedy": [None, "alpha", "beta"],
                        "max_turns": {"min": 1, "max": 512, "default": 128},
                    },
                }
            )

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

        if self.path.startswith("/sprites/"):
            key = unquote(self.path.removeprefix("/sprites/").split("?", 1)[0])

            if not key or "/" in key or "\\" in key:
                self.send_error(400, "invalid sprite key")

                return

            by_species, _by_file = _sprite_lookup()
            image_url = by_species.get(key)

            if not image_url:
                self.send_error(404, "sprite not found")

                return

            try:
                req = Request(image_url, headers={"User-Agent": "VGC-RL/1.0"})
                with urlopen(req, timeout=20) as remote:
                    body = remote.read()
                    ctype = remote.headers.get("Content-Type") or "image/png"
            except OSError:
                self.send_error(502, "sprite upstream failed")

                return

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(body)

            return

        return super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/simulate":
            self.send_error(404)

            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid content length")

            return

        raw = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(raw.decode("utf-8") if raw else "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON body"}, status=400)

            return

        if not isinstance(body, dict):
            self._send_json({"error": "body must be a JSON object"}, status=400)

            return

        alpha_default, beta_default = default_viewer_team_keys()
        team_alpha_key = str(body.get("team_alpha_key") or alpha_default)
        team_beta_key = str(body.get("team_beta_key") or beta_default)
        seed = body.get("seed")

        if seed is not None:
            seed = int(seed)

        max_steps = int(body.get("max_turns") or body.get("max_steps") or 128)
        max_steps = max(1, min(512, max_steps))
        save = bool(body.get("save", True))
        six_bring = True
        meta_pool = bool(body.get("meta_pool_policies", self.meta_pool_policies))
        game = str(body.get("game") or self.game)

        if game not in ("champions", "sv"):
            self._send_json({"error": "game must be champions or sv"}, status=400)

            return

        alpha_det = bool(body.get("alpha_deterministic", not body.get("alpha_stochastic", False)))
        beta_det = bool(body.get("beta_deterministic", not body.get("beta_stochastic", False)))
        vs_greedy = body.get("vs_greedy")

        if vs_greedy is not None and vs_greedy not in ("", "alpha", "beta"):
            self._send_json({"error": "vs_greedy must be alpha, beta, or omitted"}, status=400)

            return

        if vs_greedy == "":
            vs_greedy = None

        alpha_det, beta_det = apply_vs_greedy(vs_greedy=vs_greedy, alpha_deterministic=alpha_det, beta_deterministic=beta_det)

        if "live_oracle" in body:
            fake_oracle = not bool(body["live_oracle"])
        else:
            fake_oracle = self.fake_oracle

        try:
            alpha_policy_name = body.get("alpha_policy")
            beta_policy_name = body.get("beta_policy")
            alpha_path = resolve_policy_path(
                self.policy_dir,
                side="alpha",
                filename=None if alpha_policy_name in (None, "", "auto") else str(alpha_policy_name),
                team_alpha_key=team_alpha_key,
                team_beta_key=team_beta_key,
                game=game,
                six_bring=six_bring,
                meta_pool=meta_pool,
                default_alpha=self.default_alpha_policy,
                default_beta=None,
            )
            beta_path = resolve_policy_path(
                self.policy_dir,
                side="beta",
                filename=None if beta_policy_name in (None, "", "auto") else str(beta_policy_name),
                team_alpha_key=team_alpha_key,
                team_beta_key=team_beta_key,
                game=game,
                six_bring=six_bring,
                meta_pool=meta_pool,
                default_alpha=None,
                default_beta=self.default_beta_policy,
            )
            doc = simulate_ai_replay(
                team_alpha_key=team_alpha_key,
                team_beta_key=team_beta_key,
                alpha_policy_path=alpha_path,
                beta_policy_path=beta_path,
                seed=seed,
                max_steps=max_steps,
                game=game,
                fake_oracle=fake_oracle,
                oracle_url=self.oracle_url,
                alpha_deterministic=alpha_det,
                beta_deterministic=beta_det,
                allow_mega_evolution=bool(body.get("allow_mega_evolution", body.get("allow_mega", True))),
                allow_terastal=bool(body.get("allow_terastal", body.get("allow_tera", True))),
                random_bring_alpha=bool(body.get("random_bring_alpha", False)),
                random_bring_beta=bool(body.get("random_bring_beta", False)),
            )
        except FileNotFoundError as exc:
            self._send_json({"error": str(exc)}, status=404)

            return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)

            return
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, status=503)

            return

        saved_name: str | None = None

        if save:
            stamp = int(time.time() * 1000)
            saved_name = f"simulate_{team_alpha_key}_vs_{team_beta_key}_{stamp}.json"
            write_replay(self.replay_dir / saved_name, doc)

        self._send_json({"replay": doc, "saved_as": saved_name})

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def guess_type(self, path: str) -> str:
        ctype = mimetypes.guess_type(path)[0]

        if ctype:
            return ctype

        return "application/octet-stream"


def serve_replay_viewer(
    *,
    replay_dir: Path,
    host: str,
    port: int,
    policy_dir: Path | None = None,
    default_alpha_policy: Path | None = None,
    default_beta_policy: Path | None = None,
    fake_oracle: bool = True,
    oracle_url: str | None = None,
    game: str = "champions",
    meta_pool_policies: bool = True,
) -> None:
    replay_dir = replay_dir.resolve()
    replay_dir.mkdir(parents=True, exist_ok=True)
    viewer = _viewer_root()
    resolved_policy_dir = (policy_dir or replay_dir.parent).resolve()

    if default_alpha_policy is None:
        candidate = resolved_policy_dir / "alpha_alpha_vs_beta_champions_bring6_meta.zip"

        if candidate.is_file():
            default_alpha_policy = candidate

    if default_beta_policy is None:
        candidate = resolved_policy_dir / "beta_beta_vs_alpha_champions_bring6_meta.zip"

        if candidate.is_file():
            default_beta_policy = candidate

    handler_cls = type(
        "BoundReplayViewerHandler",
        (ReplayViewerHandler,),
        {
            "replay_dir": replay_dir,
            "policy_dir": resolved_policy_dir,
            "default_alpha_policy": default_alpha_policy,
            "default_beta_policy": default_beta_policy,
            "fake_oracle": fake_oracle,
            "oracle_url": oracle_url,
            "game": game,
            "meta_pool_policies": meta_pool_policies,
        },
    )
    handler = partial(handler_cls, directory=str(viewer))
    server = ThreadingHTTPServer((host, port), handler)

    print(
        f"Replay viewer · http://{host}:{port}/ · replays → {replay_dir} · policies → {resolved_policy_dir}",
        flush=True,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the VGC RL browser replay viewer.")
    parser.add_argument("--replay-dir", type=Path, default=Path("replays"), help="Directory with saved replay JSON files")
    parser.add_argument("--policy-dir", type=Path, default=None, help="Directory with MaskablePPO zip checkpoints (default: parent of replay-dir)")
    parser.add_argument("--alpha-policy", type=Path, default=None, help="Default Alpha policy zip")
    parser.add_argument("--beta-policy", type=Path, default=None, help="Default Beta policy zip")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--live-oracle", action="store_true", help="Use oracle-server instead of FakeOracleClient for simulation")
    parser.add_argument("--oracle-url", default=None, help="Oracle base URL when --live-oracle is set")
    parser.add_argument("--sv", action="store_true", help="Use Scarlet/Violet rules for simulation")
    parser.add_argument(
        "--named-policies",
        action="store_true",
        help="Resolve policy zips from team keys (default: use meta-pool bring6_meta filenames when present)",
    )
    args = parser.parse_args(argv)

    serve_replay_viewer(
        replay_dir=args.replay_dir,
        host=args.host,
        port=args.port,
        policy_dir=args.policy_dir,
        default_alpha_policy=args.alpha_policy,
        default_beta_policy=args.beta_policy,
        fake_oracle=not args.live_oracle,
        oracle_url=args.oracle_url,
        game="sv" if args.sv else "champions",
        meta_pool_policies=not args.named_policies,
    )

    return 0
