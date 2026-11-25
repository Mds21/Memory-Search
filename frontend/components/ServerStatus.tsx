"use client";
import { CloudOff, RotateCw } from "lucide-react";
import { useEffect, useState } from "react";
import { API, server } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/** Shown while the library server can't be reached (computer asleep, internet down, link restarting). Says plainly
 *  that the files are safe, keeps checking, and reloads the page once the server answers again. */
export default function ServerStatus() {
  const { t } = useI18n();
  const [online, setOnline] = useState(true);
  const [checking, setChecking] = useState(false);

  useEffect(() => server.subscribe(setOnline), []);

  const check = async () => {
    setChecking(true);
    try {
      const r = await fetch(`${API}/auth/providers`, { cache: "no-store" });
      if (r.ok) {
        server.set(true);
        location.reload(); // pages that waited for the server load their data again
        return;
      }
    } catch { /* still unreachable */ }
    setChecking(false);
  };

  useEffect(() => {
    if (online) return;
    const id = setInterval(check, 8000);
    return () => clearInterval(id);
  }, [online]); // eslint-disable-line react-hooks/exhaustive-deps

  if (online) return null;
  return (
    <div role="status" aria-live="polite"
      className="fixed inset-x-3 bottom-3 z-[60] mx-auto flex max-w-xl items-start gap-3 rounded border border-paper-line bg-paper-card px-4 py-3 text-[13px] text-ink shadow-lift sm:bottom-5">
      <CloudOff className="mt-0.5 h-4 w-4 shrink-0 text-tide" strokeWidth={1.75} />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t("server.offline")}</p>
        <p className="mt-0.5 text-ink-mute">{t("server.offlineHint")}</p>
      </div>
      <button className="btn-ghost shrink-0" onClick={check} disabled={checking}>
        <RotateCw className={`h-4 w-4 ${checking ? "animate-spin" : ""}`} strokeWidth={1.75} />{t("server.retry")}
      </button>
    </div>
  );
}
