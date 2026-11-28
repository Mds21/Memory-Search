"""Deploy the backend to an Oracle Cloud (or any Ubuntu) server and point the Vercel site at it.

    backend\\.venv\\Scripts\\python.exe deploy\\oracle\\deploy.py --ip 1.2.3.4 --key C:\\Users\\you\\.ssh\\oracle_key

What it does:
  1. packs backend/ (code only) plus the server files in this folder,
  2. first time only: snapshots the library (database, files, thumbnails) so it moves to the server,
  3. copies everything and backend/.env over SSH and runs setup-server.sh (Docker, firewall, HTTPS, start),
  4. waits until https://api-1-2-3-4.sslip.io answers, then sets the site's backend address on Vercel and redeploys.
Run it again after code changes: it updates the code and keeps the server's library as it is.
"""
from __future__ import annotations

import argparse
import io
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
HERE = Path(__file__).resolve().parent
SITE = "https://memory-search-five.vercel.app"
CODE_SKIP = {".venv", "data", "__pycache__", ".pytest_cache", ".env", "tests", "public_url.txt"}
DATA_SKIP = {"vercel-deploy", "public_url.txt", "admin-credentials.txt", "hf"}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def ssh_base(args) -> list[str]:
    return ["-i", args.key, "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30"]


def run(cmd: list[str], **kw) -> None:
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd[:3])} ... (exit {r.returncode})")


def pack_code(out: Path) -> None:
    with tarfile.open(out, "w:gz") as tar:
        def skip(ti: tarfile.TarInfo):
            parts = Path(ti.name).parts
            return None if any(p in CODE_SKIP or p.startswith("up_") for p in parts) or ti.name.endswith(".pyc") else ti
        tar.add(BACKEND, arcname="backend", filter=skip)
        for name in ("docker-compose.yml", "Caddyfile", "setup-server.sh"):
            data = (HERE / name).read_bytes().replace(b"\r\n", b"\n")  # Windows checkouts may use CRLF; bash can't
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode, ti.mtime = len(data), 0o755 if name.endswith(".sh") else 0o644, int(time.time())
            tar.addfile(ti, io.BytesIO(data))


def pack_data(out: Path) -> None:
    """A consistent copy of the library: the SQLite backup API (safe while the laptop backend runs) plus the files."""
    data = BACKEND / "data"
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "smriti.db"
        src = sqlite3.connect(data / "smriti.db")
        dst = sqlite3.connect(snap)
        src.backup(dst)
        dst.close()
        src.close()
        with tarfile.open(out, "w:gz") as tar:
            tar.add(snap, arcname="smriti.db")
            for p in data.iterdir():
                if p.name in DATA_SKIP or p.name.startswith(("smriti.db", "up_")):
                    continue
                tar.add(p, arcname=p.name)


def wait_https(url: str, minutes: int = 25) -> bool:
    end = time.time() + minutes * 60
    while time.time() < end:
        try:
            with urllib.request.urlopen(url + "/api/v1/health", timeout=15) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(15)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", required=True, help="the server's public IP address")
    ap.add_argument("--key", required=True, help="path to the SSH private key for the server")
    ap.add_argument("--user", default="ubuntu")
    ap.add_argument("--host", help="HTTPS name for the API (default: api-<ip>.sslip.io)")
    ap.add_argument("--skip-data", action="store_true", help="don't send the laptop's library")
    ap.add_argument("--skip-site", action="store_true", help="don't change the Vercel site")
    args = ap.parse_args()
    host = args.host or f"api-{args.ip.replace('.', '-')}.sslip.io"
    url = f"https://{host}"
    target = f"{args.user}@{args.ip}"
    for tool in ("ssh", "scp"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found (Windows: Settings > Apps > Optional features > OpenSSH Client)")

    with tempfile.TemporaryDirectory() as td:
        code = Path(td) / "ms-app.tgz"
        log("packing the backend ...")
        pack_code(code)
        files = [str(code)]
        if not args.skip_data:
            data = Path(td) / "ms-data.tgz"
            log("snapshotting the library ...")
            pack_data(data)
            files.append(str(data))
        log(f"copying to {args.ip} ...")
        run(["scp", *ssh_base(args), *files, f"{target}:~/"])
        run(["scp", *ssh_base(args), str(BACKEND / ".env"), f"{target}:~/ms-backend.env"])

    origins = f"{SITE},http://localhost:3000"
    remote = ("set -e; mkdir -p ~/memory-search && tar -xzf ~/ms-app.tgz -C ~/memory-search && rm ~/ms-app.tgz && "
              "mv ~/ms-backend.env ~/memory-search/backend.env && "
              f"bash ~/memory-search/setup-server.sh '{host}' '{origins}'")
    log("setting up the server (first time: installs Docker and builds, about 10 minutes) ...")
    run(["ssh", *ssh_base(args), target, remote])

    log(f"waiting for {url} ...")
    if not wait_https(url):
        sys.exit(f"{url} didn't answer. Check that ports 80 and 443 are open in the Oracle security list (README step 3), "
                 f"then look at the logs: ssh {target} 'cd memory-search && sudo docker compose logs --tail 80'")
    log(f"backend is live at {url}")

    if not args.skip_site:
        sys.path.insert(0, str(BACKEND))
        import public_link
        if not public_link.point_site_at(url):
            sys.exit("couldn't update the Vercel site; run `npx vercel login` once, then: deploy.py ... --skip-data")
    log(f"done. Site: {SITE}  Backend: {url}")


if __name__ == "__main__":
    main()
