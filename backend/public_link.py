"""Keeps the public link to this backend alive, and the Vercel site pointed at it.

The live site (Vercel) talks to the backend on this computer through a free Cloudflare quick tunnel. Quick tunnels
get a new random address every time they start and are dropped by Cloudflare after a network outage ("Tunnel not
found"), which leaves the site pointing at a dead address: the library looks empty and uploads fail. This script:

  1. starts the tunnel and waits until its address really reaches the backend,
  2. if the address changed, sets NEXT_PUBLIC_API_URL on Vercel and redeploys the site (about two minutes),
  3. checks the link every 30 seconds and starts a fresh tunnel when it dies or stops answering.

Run it instead of a bare `cloudflared tunnel ...`:   .\\.venv\\Scripts\\python.exe public_link.py
Needs: cloudflared, Node (npx) and the Vercel CLI logged in on this computer. A Cloudflare account with a named tunnel
would give a fixed address and make the redeploy step unnecessary.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parent / "frontend"
# A copy of the frontend OUTSIDE this git repository: inside it, Vercel reads the last commit's author and blocks the
# deploy when that GitHub account isn't a member of the Vercel team.
WORK = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "MemorySearch"
DEPLOY_DIR = WORK / "vercel-deploy"
STATE = WORK / "public_url.txt"                    # the address the live site was last deployed with
LOCAL = os.environ.get("BACKEND_URL", "http://localhost:8000")
HEALTH = "/api/v1/auth/providers"
CHECK_EVERY, DOWN_AFTER = 30, 4                    # restart after ~2 minutes without an answer
URL_RX = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
DEAD = ("Unauthorized: Tunnel not found",)          # Cloudflare dropped this quick tunnel: it will never come back
SKIP = {"node_modules", ".next", ".git", ".env.local", "tsconfig.tsbuildinfo"}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def cloudflared() -> str:
    for c in (shutil.which("cloudflared"), r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe"):
        if c and Path(c).exists():
            return c
    sys.exit("cloudflared is not installed (winget install Cloudflare.cloudflared)")


def npx() -> str:
    return shutil.which("npx.cmd") or shutil.which("npx") or sys.exit("Node.js (npx) is not installed")


def healthy(url: str, timeout: float = 10) -> bool:
    try:
        with urllib.request.urlopen(url + HEALTH, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


class Tunnel:
    def __init__(self):
        self.url: str | None = None
        self.dead = threading.Event()
        self.proc = subprocess.Popen([cloudflared(), "tunnel", "--no-autoupdate", "--url", LOCAL],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            if not self.url and (m := URL_RX.search(line)):
                self.url = m.group(0)
            if any(d in line for d in DEAD):
                self.dead.set()
            if " ERR " in line and "Failed to refresh DNS" not in line:
                log("tunnel: " + line.split(" ERR ", 1)[1].strip()[:160])

    def wait_url(self, timeout: float = 60) -> str | None:
        end = time.time() + timeout
        while time.time() < end and self.proc.poll() is None:
            if self.url:
                return self.url
            time.sleep(0.5)
        return None

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def vercel_token() -> str | None:
    """VERCEL_TOKEN from the environment or backend/.env; otherwise the CLI's own login (`npx vercel login`) is used."""
    if os.environ.get("VERCEL_TOKEN"):
        return os.environ["VERCEL_TOKEN"]
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("VERCEL_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


_warned = {"login": False}


def run(args: list[str], cwd: Path, *, input: str | None = None, timeout: int = 900) -> bool:
    token = vercel_token()
    r = subprocess.run([npx(), "--yes", "vercel@latest", *args, *(["--token", token] if token else [])], cwd=cwd, input=input or "",  # closed stdin: never wait on a prompt
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        out = (r.stderr or r.stdout)
        if "credentials" in out.lower() or "vercel login" in out.lower():
            if not _warned["login"]:
                log("Vercel isn't logged in on this computer, so the site can't be pointed at the new address. Run "
                    "`npx vercel login` once in a terminal (or put VERCEL_TOKEN=... in backend/.env); this keeps retrying.")
                _warned["login"] = True
        else:
            log(f"vercel {args[0]} failed: {out.strip()[-300:]}")
    return r.returncode == 0


def point_site_at(url: str) -> bool:
    """Set the site's backend address and redeploy it from a clean, git-free copy of frontend/."""
    api = url + "/api/v1"
    log(f"pointing the site at {url} ...")
    run(["env", "rm", "NEXT_PUBLIC_API_URL", "production", "--confirm-name", "NEXT_PUBLIC_API_URL"], FRONTEND, timeout=120)
    if not run(["env", "add", "NEXT_PUBLIC_API_URL", "production"], FRONTEND, input=api, timeout=120):
        return False
    WORK.mkdir(parents=True, exist_ok=True)
    if DEPLOY_DIR.exists():
        shutil.rmtree(DEPLOY_DIR)
    shutil.copytree(FRONTEND, DEPLOY_DIR, ignore=lambda _d, names: [n for n in names if n in SKIP])
    log("deploying the site (about two minutes) ...")
    if not run(["deploy", "--prod", "--yes"], DEPLOY_DIR):
        return False
    STATE.write_text(url, encoding="utf-8")
    log("site redeployed and pointing at this computer")
    return True


def main():
    if not healthy(LOCAL, timeout=5):
        log(f"warning: the backend at {LOCAL} isn't answering yet; the link will work once it is running")
    pause = 5
    while True:
        t = Tunnel()
        url = t.wait_url()
        if not url:
            log("couldn't start a tunnel (no internet?), trying again shortly")
            t.stop()
            time.sleep(pause)
            pause = min(pause * 2, 120)
            continue
        log(f"tunnel up: {url}")
        if not any(healthy(url) or time.sleep(3) for _ in range(30)):  # new addresses can take a moment to resolve
            log("the new address never answered, starting another tunnel")
            t.stop()
            continue
        pause = 5
        last = STATE.read_text(encoding="utf-8").strip() if STATE.exists() else ""
        if url != last and not point_site_at(url):
            log("couldn't update the site; will retry with the next tunnel check")
        misses = 0
        while t.proc.poll() is None and not t.dead.is_set():
            time.sleep(CHECK_EVERY)
            if (STATE.read_text(encoding="utf-8").strip() if STATE.exists() else "") != url and healthy(url):
                point_site_at(url)  # a failed redeploy earlier: try again now that we're up
            misses = 0 if healthy(url) else misses + 1
            if misses >= DOWN_AFTER:
                log("the public link stopped answering")
                break
        log("restarting the tunnel")
        t.stop()
        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
