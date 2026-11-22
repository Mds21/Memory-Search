import io
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="smriti_test_")
os.environ["DATA_DIR"] = _TMP
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123"
os.environ["WORKER_CONCURRENCY"] = "2"
os.environ["STT"] = "none"  # no model downloads in tests
os.environ["SIGNUPS_PER_HOUR"] = "1000"  # the suite creates many accounts from one address
for _k in ("GOOGLE_CLIENT_ID", "SMTP_HOST", "SMTP_FROM"):
    os.environ[_k] = ""  # tests never use the developer's real Google/email/SMS setup

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app

API = "/api/v1"


def make_photo(path: Path, color=(40, 110, 220), exif_date=None, gps=None, text=None, size=(640, 480)):
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    d.ellipse([200, 150, 440, 330], fill=(250, 220, 60))
    if text:
        d.rectangle([0, 0, size[0], 90], fill="white")
        d.text((20, 30), text, fill="black", font_size=40) if hasattr(d, "text") else None
    exif = Image.Exif()
    if exif_date:
        exif[0x8769] = {36867: exif_date}
    if gps:
        lat, lon = gps
        exif[0x8825] = {1: "N" if lat >= 0 else "S", 2: (abs(lat), 0.0, 0.0), 3: "E" if lon >= 0 else "W", 4: (abs(lon), 0.0, 0.0)}
    img.save(path, "JPEG", exif=exif)


def make_pdf(path: Path, pages: list[str]):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            c.drawString(60, y, line)
            y -= 18
        c.showPage()
    c.save()


def make_scanned_pdf(path: Path, text: str):
    img = Image.new("RGB", (1240, 800), "white")
    d = ImageDraw.Draw(img)
    y = 80
    for line in text.split("\n"):
        d.text((60, y), line, fill="black", font_size=44)
        y += 70
    img.save(path, "PDF", resolution=150)


def make_video(path: Path, seconds=4):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=15",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], capture_output=True, check=True)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def files():
    d = Path(tempfile.mkdtemp(prefix="smriti_files_"))
    make_photo(d / "IMG_20251224_101200.jpg", (40, 110, 220), "2025:12:24 10:12:00", (15.49, 73.83))   # Goa, blue
    make_photo(d / "sunset_delhi.jpg", (230, 120, 40), "2023:03:05 18:00:00", (28.61, 77.21))          # Delhi, orange
    make_pdf(d / "rental_agreement.pdf", [
        "RENTAL AGREEMENT\nThis agreement is made between the landlord and the tenant.\nThe monthly rent is 25000 rupees.",
        "SECURITY DEPOSIT\nThe tenant shall pay a refundable security deposit of 75000 rupees.\nThe deposit will be returned within 30 days of vacating the property."])
    make_scanned_pdf(d / "scanned_invoice.pdf", "INVOICE 4471\nPlumbing repair\nTotal due 1850 dollars")
    (d / "notes.txt").write_text("Grocery list for the picnic.\nBring lemonade, sandwiches and a blanket.\nThe picnic is on Sunday at the lake.")
    make_video(d / "clip_20240615.mp4")
    (d / "bad.xyz").write_text("nope")
    return d


@pytest.fixture(scope="session")
def admin(client):
    """The owner account created on first start: one-time password from the file, then a password of our own."""
    creds = (Path(_TMP) / "admin-credentials.txt").read_text()
    pw = next(ln.split(":", 1)[1].strip() for ln in creds.splitlines() if ln.startswith("one-time password"))
    r = client.post(f"{API}/auth/login", json={"identifier": "admin", "password": pw})
    assert r.status_code == 200 and r.json()["user"]["must_change_password"], r.text
    r = client.post(f"{API}/me/password", headers={"Authorization": "Bearer " + r.json()["access_token"]}, json={"new_password": "owner-pass-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def alice(client):
    r = client.post(f"{API}/auth/register", json={"email": "alice@example.com", "password": "correct horse", "display_name": "Alice"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def bob(client):
    r = client.post(f"{API}/auth/register", json={"email": "bob@example.com", "password": "battery staple"})
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def wait_ready(client, headers, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        items = client.get(f"{API}/assets?limit=200", headers=headers).json()["items"]
        if items and all(i["status"] in ("ready", "failed") for i in items):
            return items
        time.sleep(1)
    raise TimeoutError("ingestion did not finish")


@pytest.fixture(scope="session")
def library(client, alice, files):
    ups = [("files", (p.name, p.read_bytes())) for p in sorted(files.iterdir())]
    r = client.post(f"{API}/assets", headers=alice, files=ups)
    assert r.status_code == 201, r.text
    return {"upload": r.json()["items"], "assets": wait_ready(client, alice)}
