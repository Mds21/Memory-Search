# Always-on backend on Oracle Cloud (free)

The site (frontend) is on Vercel. The backend (API, database, your files, OCR and image search) runs on one free
Oracle Cloud server, so the app keeps working when your laptop is off. Cost: nothing, on the Always Free tier.

## Your part (about 15 minutes, once)

1. **Sign up** at <https://signup.cloud.oracle.com> for the Always Free tier. Pick a home region near you (for
   example India West (Mumbai) or India South (Hyderabad)); it can't be changed later. A card is asked for to check
   your identity; Always Free resources aren't charged.
2. **Create the server**: Menu > Compute > Instances > *Create instance*.
   - Image: **Canonical Ubuntu 24.04** (or 22.04).
   - Shape: *Change shape* > Ampere > **VM.Standard.A1.Flex**, **4 OCPUs, 24 GB memory** (all inside Always Free).
   - Networking: keep the defaults, with *Assign a public IPv4 address* on.
   - SSH keys: *Generate a key pair for me* and **Save private key**. Put it at `C:\Users\admin\.ssh\oracle_key`.
   - Boot volume: 100 GB is plenty (Always Free allows up to 200 GB in total).
   - *Create*. If it says **Out of capacity**, try another availability domain or try again a bit later.
3. **Open the web ports**: on the instance page click the subnet > the *Default Security List* > *Add Ingress Rules*:
   source CIDR `0.0.0.0/0`, IP protocol TCP, destination port range `80,443`. Save.
4. Copy the instance's **Public IP address**.

## Deploy (one command, from the project folder on the laptop)

```powershell
backend\.venv\Scripts\python.exe deploy\oracle\deploy.py --ip <PUBLIC-IP> --key C:\Users\admin\.ssh\oracle_key
```

It copies the backend and your current library to the server, installs Docker, starts the API behind HTTPS at
`https://api-<ip-with-dashes>.sslip.io`, and points the Vercel site at it. The first run takes 10 to 15 minutes
(building, plus a one-time 1.7 GB download of the image model). After that the laptop isn't needed; stop the
`public link` and `backend` terminal tabs.

Updating later: run the same command with `--skip-data`. Code is replaced; the server's library is kept.

## Good to know

- The server restarts the app by itself after crashes and reboots (`restart: unless-stopped`).
- Your files live on the server in `~/memory-search/data`. Back it up from time to time:
  `ssh -i <key> ubuntu@<ip> "sudo tar czf - -C memory-search data" > memory-search-backup.tgz`
- Logs: `ssh -i <key> ubuntu@<ip> "cd memory-search && sudo docker compose logs --tail 100 backend"`
- Google sign-in needs no change: Google only checks the site's address (memory-search-five.vercel.app).
- Oracle may reclaim Always Free instances that sit nearly idle for a long time; normal use, and the image model
  loading at start, usually keeps it active. Upgrading the account to Pay As You Go (still free within the limits) avoids this.
