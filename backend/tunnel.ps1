# Keeps the public link to this backend alive and the Vercel site pointed at it (restarts the tunnel when it drops,
# redeploys the site when the address changes). See public_link.py.
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\public_link.py"
