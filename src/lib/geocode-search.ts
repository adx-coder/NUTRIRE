import type { Coords } from "@/types";

interface GeocodeHit {
  name: string;
  latitude: number;
  longitude: number;
  country_code?: string;
  admin1?: string;
}

const DMV_ADMIN1 = new Set(["district of columbia", "maryland", "virginia"]);

function rankHit(h: GeocodeHit): number {
  const a1 = (h.admin1 ?? "").toLowerCase();
  if (h.country_code !== "US") return -1000;
  if (DMV_ADMIN1.has(a1)) return 100;
  return 0;
}

/**
 * Forward geocode (Open-Meteo search API — no API key).
 * Biases toward US + DMV-adjacent admin areas when multiple hits exist.
 */
export async function geocodeTypedLocation(query: string): Promise<{ coords: Coords; label: string } | null> {
  const q = query.trim();
  if (!q) return null;

  const url = new URL("https://geocoding-api.open-meteo.com/v1/search");
  url.searchParams.set("name", q);
  url.searchParams.set("count", "12");
  url.searchParams.set("language", "en");
  url.searchParams.set("format", "json");

  const resp = await fetch(url.toString());
  if (!resp.ok) return null;
  const json = (await resp.json()) as { results?: GeocodeHit[] };
  const hits = json.results;
  if (!hits?.length) return null;

  const sorted = [...hits].sort((a, b) => rankHit(b) - rankHit(a));
  const best = sorted[0];
  if (best.country_code && best.country_code !== "US") {
    const usOnly = sorted.find((h) => h.country_code === "US");
    if (!usOnly) return null;
    return formatResult(usOnly, q);
  }
  return formatResult(best, q);
}

function formatResult(h: GeocodeHit, originalQuery: string): { coords: Coords; label: string } {
  const parts = [h.name, h.admin1].filter(Boolean);
  const label = parts.length ? parts.join(", ") : originalQuery;
  return {
    coords: { lat: h.latitude, lng: h.longitude },
    label,
  };
}
