import { useState, useRef, useEffect } from "react";
import { MapPin, Loader2, ArrowRight, Navigation } from "lucide-react";
import clsx from "clsx";
import { useLocationStore } from "@/store/location";
import { mockUserLocation } from "@/data/load-data";
import { useT } from "@/i18n/useT";

const DMV_CENTER = mockUserLocation; // fallback if geocode fails

async function geocodeQuery(query: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const q = encodeURIComponent(`${query}, Washington DC metro area`);
    const resp = await fetch(`https://nominatim.openstreetmap.org/search?q=${q}&format=json&limit=1&countrycodes=us`, {
      headers: { "User-Agent": "Nutrire-FoodAccess/1.0" },
    });
    const results = await resp.json();
    if (results.length > 0) {
      return { lat: parseFloat(results[0].lat), lng: parseFloat(results[0].lon) };
    }
  } catch {}
  return null;
}

interface Props {
  onSubmit: () => void;
  autoFocus?: boolean;
}

/**
 * Location input for the main search entry point.
 */
export function LocationInput({ onSubmit, autoFocus = true }: Props) {
  const [value, setValue] = useState("");
  const [geolocating, setGeolocating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const setLocation = useLocationStore((s) => s.setLocation);
  const t = useT();

  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  const nearbyLabel = t("home.input.nearMe");
  const useCurrentLocationLabel = t("home.input.useMyLocation");
  const usingLocationLabel = t("home.input.usingLocation");

  const [submitting, setSubmitting] = useState(false);

  const submitTyped = async () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setSubmitting(true);
    const coords = await geocodeQuery(trimmed);
    setLocation({ coords: coords ?? DMV_CENTER, label: trimmed, source: coords ? "geolocate" : "typed" });
    setSubmitting(false);
    onSubmit();
  };

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      setLocation({ coords: mockUserLocation, label: nearbyLabel, source: "default" });
      onSubmit();
      return;
    }

    setGeolocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          coords: { lat: pos.coords.latitude, lng: pos.coords.longitude },
          label: nearbyLabel,
          source: "geolocate",
        });
        setGeolocating(false);
        onSubmit();
      },
      () => {
        setLocation({ coords: mockUserLocation, label: nearbyLabel, source: "default" });
        setGeolocating(false);
        onSubmit();
      },
      { timeout: 8000, maximumAge: 60_000 },
    );
  };

  return (
    <div className="w-full">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submitTyped();
        }}
        className={clsx(
          "group relative flex items-center gap-3 w-full",
          "h-[54px] pl-5 pr-1.5 rounded-full",
          "bg-white/35 backdrop-blur-2xl border border-white/45",
          "shadow-[0_4px_20px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.6)]",
          "focus-within:border-sage/25 focus-within:bg-white/45 focus-within:shadow-[0_6px_24px_rgba(79,127,106,0.1)]",
          "transition-all duration-300",
        )}
      >
        <MapPin size={18} className="text-sage-deep/70 shrink-0" aria-hidden="true" strokeWidth={2} />
        <input
          ref={inputRef}
          type="text"
          inputMode="text"
          autoComplete="street-address"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t("home.input.placeholder")}
          aria-label={t("home.input.locationAria")}
          className="flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-muted/70 outline-none min-w-0"
        />

        <button
          type="button"
          onClick={useMyLocation}
          disabled={geolocating}
          aria-label={useCurrentLocationLabel}
          className={clsx(
            "hidden sm:inline-flex items-center gap-1.5 shrink-0",
            "h-9 px-3 rounded-full",
            "text-[12px] font-medium text-sage-deep/70",
            "bg-white/30 border border-white/40 backdrop-blur-lg",
            "hover:bg-white/50 hover:text-sage-deep transition-all",
            "disabled:opacity-50",
          )}
        >
          {geolocating ? (
            <Loader2 size={13} className="animate-spin" aria-hidden="true" />
          ) : (
            <Navigation size={13} aria-hidden="true" />
          )}
          <span>{nearbyLabel}</span>
        </button>

        <button
          type="submit"
          aria-label={t("home.input.submitAria")}
          className={clsx(
            "shrink-0 h-10 w-10 rounded-full",
            "flex items-center justify-center",
            "bg-sage-deep text-white",
            "hover:brightness-110 active:scale-[0.94]",
            "transition-all duration-200",
            "shadow-[0_2px_8px_rgba(58,101,81,0.3)]",
            "disabled:opacity-30 disabled:pointer-events-none",
          )}
          disabled={!value.trim() || submitting}
        >
          {submitting ? <Loader2 size={18} className="animate-spin" aria-hidden="true" /> : <ArrowRight size={18} strokeWidth={2.5} aria-hidden="true" />}
        </button>
      </form>

      <button
        type="button"
        onClick={useMyLocation}
        disabled={geolocating}
        className="sm:hidden mt-3 inline-flex items-center gap-2 text-sm text-sage-deep font-medium hover:underline disabled:opacity-60 min-h-[44px]"
      >
        {geolocating ? (
          <>
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            {usingLocationLabel}
          </>
        ) : (
          <>
            <Navigation size={14} aria-hidden="true" />
            {useCurrentLocationLabel}
          </>
        )}
      </button>
    </div>
  );
}
