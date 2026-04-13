import type { EnrichedOrganization, RankedOrg, Coords, LangCode, ServiceType } from "@/types";
import { haversineMeters, walkMinutes as toWalkMin, driveMinutes as toDriveMin, metersToMiles } from "./geo";
import { computeOpenStatus } from "./open-status";

export type RankMode = "closest" | "most_private" | "most_welcoming";

export interface RankOrgOptions {
  userLocation: Coords;
  now?: Date;
  mode?: RankMode;
  languages?: LangCode[];
  maxResults?: number;
  /** If set, boost orgs offering these services (from suggestion chips) */
  preferServices?: ServiceType[];
}

export function rankOrgs(orgs: EnrichedOrganization[], opts: RankOrgOptions): RankedOrg[] {
  const now = opts.now ?? new Date();
  const mode = opts.mode ?? "closest";
  const userLangs = opts.languages ?? ["en"];
  const max = opts.maxResults ?? 30;
  const preferSvc = opts.preferServices ?? [];

  const results: RankedOrg[] = [];

  for (const org of orgs) {
    const meters = haversineMeters(opts.userLocation, { lat: org.lat, lng: org.lon });
    if (isNaN(meters)) continue; // skip orgs with bad coords
    const walk = toWalkMin(meters);
    const drive = toDriveMin(meters);
    const openStatus = computeOpenStatus(org, now);

    const transit = estimateTransit(org, meters);

    const miles = metersToMiles(meters);
    const proximity = Math.max(0, 1 - miles / 8);

    let timing: number;
    switch (openStatus.state) {
      case "open": timing = 1.0; break;
      case "opens_today": timing = 0.85; break;
      case "opens_this_week": timing = 0.5; break;
      default: timing = 0.2;
    }

    const reqs = org.accessRequirements;
    let friction = 0;
    if (reqs.includes("appointment_required")) friction += 0.35;
    if (reqs.includes("photo_id")) friction += 0.2;
    if (reqs.includes("proof_of_address")) friction += 0.15;
    if (reqs.includes("income_verification")) friction += 0.2;
    const ease = 1 - Math.min(friction, 1);

    const trust = org.reliability.score;
    const langMatch = org.languages.some((l) => userLangs.includes(l)) ? 1 : 0.5;
    const tone = org.ai.toneScore;

    // Service match: 1.0 if org offers ANY preferred service, 0.5 if not, 1.0 if no preference set
    const svcMatch = preferSvc.length === 0
      ? 1.0
      : org.services.some((s) => preferSvc.includes(s)) ? 1.0 : 0.15;

    const w = preferSvc.length > 0
      // When user has an intent, service match dominates
      ? { proximity: 0.20, timing: 0.20, ease: 0.05, trust: 0.10, lang: 0.05, tone: 0.05, svc: 0.35 }
      : mode === "closest"
      ? { proximity: 0.30, timing: 0.25, ease: 0.10, trust: 0.15, lang: 0.10, tone: 0.10, svc: 0 }
      : mode === "most_private"
      ? { proximity: 0.15, timing: 0.15, ease: 0.30, trust: 0.10, lang: 0.10, tone: 0.20, svc: 0 }
      : { proximity: 0.20, timing: 0.15, ease: 0.25, trust: 0.10, lang: 0.10, tone: 0.20, svc: 0 };

    const score =
      proximity * w.proximity +
      timing * w.timing +
      ease * w.ease +
      trust * w.trust +
      langMatch * w.lang +
      tone * w.tone +
      svcMatch * w.svc;

    results.push({
      org,
      distanceMeters: meters,
      walkMinutes: walk,
      transitMinutes: transit,
      driveMinutes: drive,
      openStatus,
      why: explain(org, walk, openStatus, userLangs),
      score,
    });
  }

  // Primary sort: open status tier (open > opens_today > opens_this_week > rest)
  // Secondary sort: proximity (closest first within each tier)
  const openTierRank = (state: string): number => {
    switch (state) {
      case "open": return 0;
      case "opens_today": return 1;
      case "opens_this_week": return 2;
      default: return 3;
    }
  };

  results.sort((a, b) => {
    const tierA = openTierRank(a.openStatus.state);
    const tierB = openTierRank(b.openStatus.state);
    if (tierA !== tierB) return tierA - tierB;
    // Within same tier, sort by distance (closest first)
    return a.distanceMeters - b.distanceMeters;
  });

  return results.slice(0, max);
}

function estimateTransit(org: EnrichedOrganization, meters: number): number | null {
  if (!org.nearestTransit) return null;
  // nearestTransit may be a string (stop name) or an object { name, distanceMeters, walkMinutes }
  const walkToStop = typeof org.nearestTransit === "string"
    ? 5 // default estimate when only stop name is available
    : (org.nearestTransit.walkMinutes ?? Math.round(org.nearestTransit.distanceMeters / 80));
  const busMiles = metersToMiles(meters);
  const busMinutes = Math.round((busMiles / 15) * 60);
  return walkToStop + busMinutes;
}

function explain(
  org: EnrichedOrganization,
  walk: number,
  status: ReturnType<typeof computeOpenStatus>,
  userLangs: LangCode[],
): string {
  const parts: string[] = [];

  if (walk <= 20) parts.push(`${walk} min walk`);
  else if (org.nearestTransit) {
    const raw = typeof org.nearestTransit === "string" ? org.nearestTransit : org.nearestTransit.name;
    const name = raw.split(" (")[0];
    parts.push(`near ${name}`);
  }

  if (status.state === "open") parts.push("open now");
  else if (status.state === "opens_today") parts.push("opens today");

  if (
    !org.accessRequirements.includes("appointment_required") &&
    (org.accessRequirements.includes("no_id_required") || !org.accessRequirements.includes("photo_id"))
  ) {
    parts.push("no ID needed");
  }

  const matchedLang = org.languages.find((l) => userLangs.includes(l) && l !== "en");
  if (matchedLang === "es") parts.push("Spanish spoken");
  else if (matchedLang === "am") parts.push("Amharic spoken");

  return parts.length > 0 ? parts.join(", ") + "." : "";
}
