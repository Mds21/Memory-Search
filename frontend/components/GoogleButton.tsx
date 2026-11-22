"use client";
import { useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

declare global { interface Window { google?: any } }

let scriptLoad: Promise<void> | null = null;
let initializedFor: string | null = null;                  // Google's script is set up once per client id
let currentCallback: ((credential: string) => void) | null = null;  // the mounted button's handler
function loadGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  scriptLoad ||= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true; s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => { scriptLoad = null; reject(new Error("load")); };
    document.head.appendChild(s);
  });
  return scriptLoad;
}

export const GoogleG = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden>
    <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.6 13.3l7.9 6.2C12.4 13.7 17.7 9.5 24 9.5z" />
    <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.7 6c4.5-4.2 6.9-10.3 6.9-17.7z" />
    <path fill="#FBBC05" d="M10.5 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.2C.9 16.6 0 20.2 0 24s.9 7.4 2.6 10.8l7.9-6.2z" />
    <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.7-6c-2.1 1.4-4.9 2.3-8.2 2.3-6.3 0-11.6-4.2-13.5-10l-7.9 6.2C6.6 42.6 14.6 48 24 48z" />
  </svg>
);

/**
 * "Continue with Google". Always shown. When the owner has switched Google sign-in on, it is Google's own button
 * (plus One Tap); Google returns a signed ID token and the server verifies it. Until then, a click explains why.
 */
export default function GoogleButton({ onCredential }: { onCredential: (credential: string) => void }) {
  const { t, lang } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const cb = useRef(onCredential);
  cb.current = onCredential;
  const [clientId, setClientId] = useState<string | null | undefined>(undefined);
  const [rendered, setRendered] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    fetch(`${API}/auth/providers`).then((r) => r.json()).then((d) => setClientId(d.google_client_id || null)).catch(() => setClientId(null));
  }, []);

  useEffect(() => {
    if (!clientId || !box.current) return;
    let cancelled = false;
    loadGis().then(() => {
      if (cancelled || !box.current) return;
      const g = window.google.accounts.id;
      if (initializedFor !== clientId) {  // Google warns (and misbehaves) if initialize() runs more than once
        initializedFor = clientId;
        g.initialize({ client_id: clientId, callback: (r: { credential: string }) => currentCallback?.(r.credential), ux_mode: "popup",
                       auto_select: false, itp_support: true, use_fedcm_for_prompt: true });
        g.prompt();  // One Tap: returning users sign in with a single tap
      }
      currentCallback = (c: string) => cb.current(c);
      const dark = document.documentElement.dataset.theme === "dark";
      box.current.innerHTML = "";
      g.renderButton(box.current, { type: "standard", theme: dark ? "filled_black" : "outline", size: "large", shape: "pill",
                                    text: "continue_with", logo_alignment: "center", width: Math.min(400, box.current.offsetWidth || 320), locale: lang });
      setRendered(true);
    }).catch(() => !cancelled && setNote(t("auth.googleOffline")));
    return () => { cancelled = true; };
  }, [clientId, lang, t]);

  return (
    <div className="space-y-2">
      <div ref={box} className={`w-full justify-center ${rendered ? "flex min-h-[44px]" : "hidden"}`} />
      {!rendered && (
        <button type="button" disabled={clientId === undefined}
          onClick={() => setNote(clientId ? t("auth.googleOffline") : t("auth.googleOff"))}
          className="tap flex h-11 w-full items-center justify-center gap-3 rounded-full border border-paper-line bg-paper-card text-sm font-medium text-ink shadow-soft transition-colors hover:bg-paper-sunk disabled:opacity-60">
          <GoogleG />{t("auth.google")}
        </button>)}
      {note && <p role="status" className="animate-fade-in rounded-xl bg-paper-sunk px-3 py-2 text-center text-xs leading-relaxed text-ink-soft">{note}</p>}
    </div>
  );
}
