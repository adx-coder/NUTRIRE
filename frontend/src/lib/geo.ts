import type { Coords } from "@/types";

const EARTH_M = 6371000;

/** Haversine distance in meters. */
export function haversineMeters(a: Coords, b: Coords): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_M * Math.asin(Math.sqrt(h));
}

export function metersToMiles(m: number): number {
  return m / 1609.344;
}

export function metersToKm(m: number): number {
  return m / 1000;
}

/** Naive walk-time estimate: 1.4 m/s (average adult walking speed) with a 1.2x friction factor for urban. */
export function walkMinutes(meters: number): number {
  const secondsPerMeter = 1 / (1.4 / 1.2);
  return Math.round((meters * secondsPerMeter) / 60);
}

/** Naive drive-time: 30 km/h urban average. */
export function driveMinutes(meters: number): number {
  const kph = 30;
  const hours = metersToKm(meters) / kph;
  return Math.max(2, Math.round(hours * 60));
}
