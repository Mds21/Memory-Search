"use client";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { Empty, Spinner } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";

interface Cluster { lat: number; lon: number; count: number; place: string | null; asset: Asset; asset_ids: string[] }

export default function MapPage() {
  const { t } = useI18n();
  const el = useRef<HTMLDivElement>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [picked, setPicked] = useState<Asset[]>([]);
  const viewer = useViewer(picked);
  const openRef = useRef(viewer.open);
  openRef.current = viewer.open;

  useEffect(() => {
    let map: any; let markers: any[] = []; let dead = false; let maplibre: any;
    (async () => {
      maplibre = (await import("maplibre-gl")).default;
      if (dead || !el.current) return;
      map = new maplibre.Map({
        container: el.current, center: [78, 22], zoom: 3.2,
        style: { version: 8, sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" } }, layers: [{ id: "osm", type: "raster", source: "osm" }] },
      });
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
      let fitted = false;
      const refresh = async () => {
        const b = map.getBounds();
        const r = await api.get<{ clusters: Cluster[]; total: number }>(`/map/clusters?min_lat=${b.getSouth()}&min_lon=${b.getWest()}&max_lat=${b.getNorth()}&max_lon=${b.getEast()}&zoom=${Math.round(map.getZoom())}`);
        if (dead) return;
        setTotal((x) => (x === null || r.total > 0 ? r.total : x));
        markers.forEach((m) => m.remove()); markers = [];
        for (const c of r.clusters) {
          const d = document.createElement("button");
          d.className = "relative h-12 w-12 rounded-full border-2 border-white bg-tide bg-cover bg-center shadow-lift";
          d.setAttribute("aria-label", `${c.place || ""} ${c.count}`);
          if (c.asset.thumb_url) d.style.backgroundImage = `url(${abs(c.asset.thumb_url)})`;
          if (c.count > 1) { const n = document.createElement("span"); n.textContent = String(c.count); n.className = "absolute -right-1 -top-1 rounded-full bg-night px-1.5 text-[11px] font-semibold text-white"; d.appendChild(n); }
          d.onclick = async () => {
            if (c.count > 1 && map.getZoom() < 14) return map.easeTo({ center: [c.lon, c.lat], zoom: map.getZoom() + 2.5 });
            const cards = await Promise.all(c.asset_ids.slice(0, 40).map((id) => api.get<Asset>(`/assets/${id}`)));
            setPicked(cards); setTimeout(() => openRef.current(cards[0]), 0);
          };
          markers.push(new maplibre.Marker({ element: d }).setLngLat([c.lon, c.lat]).addTo(map));
        }
        if (!fitted && r.clusters.length) { fitted = true; const bb = new maplibre.LngLatBounds(); r.clusters.forEach((c) => bb.extend([c.lon, c.lat])); map.fitBounds(bb, { padding: 80, maxZoom: 11, duration: 0 }); }
      };
      map.on("moveend", refresh); map.once("load", refresh);
    })();
    return () => { dead = true; map?.remove(); };
  }, []);

  return (
    <div className="flex h-[calc(100dvh-3.5rem-5.5rem-env(safe-area-inset-bottom))] flex-col lg:h-screen">
      <div className="flex items-center gap-3 px-4 py-2.5 sm:px-6 sm:py-3"><h1 className="h-page max-lg:hidden">{t("map.title")}</h1>{total === null && <Spinner />}{total ? <span className="text-sm text-ink-mute">{total} {t("common.photos")}</span> : null}</div>
      <div className="relative min-h-0 flex-1"><div ref={el} className="absolute inset-0" />
        {total === 0 && <div className="pointer-events-none absolute inset-x-4 top-4 mx-auto max-w-md rounded-xl bg-paper-card/95 p-4 shadow-lift"><Empty title={t("map.empty")} /></div>}</div>
      {viewer.node}
    </div>
  );
}
