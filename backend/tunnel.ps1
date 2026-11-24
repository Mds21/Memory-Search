# Exposes the local backend (port 8000) at a public https address for the Vercel site.
# Quick tunnels get a new random address each start; set it as NEXT_PUBLIC_API_URL on Vercel and redeploy.
& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --no-autoupdate --url http://localhost:8000
