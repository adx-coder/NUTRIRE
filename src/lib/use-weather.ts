import { useState, useEffect } from "react";

export interface Weather {
  temp: number; // °F
  code: number; // WMO weather code
  label: string;
  isAdverse: boolean; // rain, snow, storm — travel may be affected
}

// WMO Weather interpretation codes → label + adverse flag
function interpretCode(code: number): { label: string; isAdverse: boolean } {
  if (code === 0) return { label: "Clear sky", isAdverse: false };
  if (code <= 3) return { label: "Partly cloudy", isAdverse: false };
  if (code <= 48) return { label: "Foggy", isAdverse: true };
  if (code <= 55) return { label: "Drizzle", isAdverse: true };
  if (code <= 57) return { label: "Freezing drizzle", isAdverse: true };
  if (code <= 65) return { label: "Rain", isAdverse: true };
  if (code <= 67) return { label: "Freezing rain", isAdverse: true };
  if (code <= 75) return { label: "Snow", isAdverse: true };
  if (code === 77) return { label: "Snow grains", isAdverse: true };
  if (code <= 82) return { label: "Rain showers", isAdverse: true };
  if (code <= 86) return { label: "Snow showers", isAdverse: true };
  if (code === 95) return { label: "Thunderstorm", isAdverse: true };
  if (code <= 99) return { label: "Thunderstorm with hail", isAdverse: true };
  return { label: "Unknown", isAdverse: false };
}

const cache = new Map<string, { data: Weather; ts: number }>();
const TTL = 10 * 60 * 1000; // 10 min cache

export function useWeather(lat: number | undefined, lon: number | undefined): Weather | null {
  const [weather, setWeather] = useState<Weather | null>(null);

  useEffect(() => {
    if (!lat || !lon) return;

    const key = `${lat.toFixed(2)},${lon.toFixed(2)}`;
    const cached = cache.get(key);
    if (cached && Date.now() - cached.ts < TTL) {
      setWeather(cached.data);
      return;
    }

    let cancelled = false;

    fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code&temperature_unit=fahrenheit&timezone=auto`
    )
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        const current = json?.current;
        if (!current) return;

        const temp = Math.round(current.temperature_2m);
        const code = current.weather_code ?? 0;
        const { label, isAdverse } = interpretCode(code);
        const data: Weather = { temp, code, label, isAdverse };

        cache.set(key, { data, ts: Date.now() });
        setWeather(data);
      })
      .catch(() => {}); // silent fail — weather is non-critical

    return () => { cancelled = true; };
  }, [lat, lon]);

  return weather;
}
