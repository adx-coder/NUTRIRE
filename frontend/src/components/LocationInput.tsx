import { useState, useRef, useEffect } from "react";
import { MapPin, Loader2, ArrowRight, Navigation } from "lucide-react";
import clsx from "clsx";
import { useLocationStore } from "@/store/location";
import { mockUserLocation } from "@/data/load-data";

interface Props {
  onSubmit: () => void;
  autoFocus?: boolean;
}

/**
 * LocationInput — the single most important input in the app.
 * Design ref: DESIGN.md §3.5 (upgraded for premium feel).
 *
 *  Height 64px, pill shape, shadow, embedded submit button on the right.
 *  22px map-pin icon on the left. Placeholder: "Where are you?"
 *  Autofocus on Home. Submit on Enter or by tapping the arrow.
 *  "Use my location" as a secondary button inline on the right.
 */
export function LocationInput({ onSubmit, autoFocus = true }: Props) {
  const [value, setValue] = useState("");
  const [geolocating, setGeolocating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const setLocation = useLocationStore((s) => s.setLocation);

  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  const submitTyped = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setLocation({ coords: mockUserLocation, label: trimmed, source: "typed" });
    onSubmit();
  };

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      setLocation({ coords: mockUserLocation, label: "Near you", source: "default" });
      onSubmit();
      return;
    }
    setGeolocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          coords: { lat: pos.coords.latitude, lng: pos.coords.longitude },
          label: "Near you",
          source: "geolocate",
        });
        setGeolocating(false);
        onSubmit();
      },
      () => {
        setLocation({ coords: mockUserLocation, label: "Near you", source: "default" });
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
          autoComplete="postal-code"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter your ZIP or neighborhood"
          aria-label="Where are you?"
          className="flex-1 bg-transparent text-[15px] text-ink placeholder:text-ink-muted/70 outline-none min-w-0"
        />

        {/* Near me */}
        <button
          type="button"
          onClick={useMyLocation}
          disabled={geolocating}
          aria-label="Use my current location"
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
          <span>Near me</span>
        </button>

        {/* Submit */}
        <button
          type="submit"
          aria-label="Find food near this location"
          className={clsx(
            "shrink-0 h-10 w-10 rounded-full",
            "flex items-center justify-center",
            "bg-sage-deep text-white",
            "hover:brightness-110 active:scale-[0.94]",
            "transition-all duration-200",
            "shadow-[0_2px_8px_rgba(58,101,81,0.3)]",
            "disabled:opacity-30 disabled:pointer-events-none",
          )}
          disabled={!value.trim()}
        >
          <ArrowRight size={18} strokeWidth={2.5} aria-hidden="true" />
        </button>
      </form>

      {/* Mobile fallback: plain text button below the input */}
      <button
        type="button"
        onClick={useMyLocation}
        disabled={geolocating}
        className="sm:hidden mt-3 inline-flex items-center gap-2 text-sm text-sage-deep font-medium hover:underline disabled:opacity-60 min-h-[44px]"
      >
        {geolocating ? (
          <>
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            One moment...
          </>
        ) : (
          <>
            <Navigation size={14} aria-hidden="true" />
            Use my current location
          </>
        )}
      </button>
    </div>
  );
}
