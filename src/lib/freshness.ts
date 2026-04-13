import type { ConfidenceSignal, ReliabilitySignal } from "@/types";
import { relativeTimeShort } from "./time";

export type FreshnessTone = {
  dotColor: string;
  label: string;
  labelKey?: string;
  labelVars?: Record<string, string | number>;
  shouldPromote: boolean;
  urgentCall: boolean;
};

/**
 * Maps a ConfidenceSignal tier to display properties (dot colour, label, CTA behaviour).
 * "verified" and "likely" are safe to show as-is; "stale" and "unknown" always
 * prompt the user to call ahead before visiting.
 */
export function freshnessTone(c: ConfidenceSignal): FreshnessTone {
  switch (c.tier) {
    case "verified":
      return { dotColor: "var(--sage)", label: c.humanExplanation, shouldPromote: true, urgentCall: false };
    case "likely":
      return { dotColor: "var(--mustard)", label: c.humanExplanation, shouldPromote: true, urgentCall: false };
    case "stale":
      return { dotColor: "var(--stone)", label: "We haven't confirmed this recently. Call first.", shouldPromote: false, urgentCall: true };
    case "unknown":
    default:
      return { dotColor: "var(--stone)", label: "We haven't been able to check this one. Call first.", shouldPromote: false, urgentCall: true };
  }
}

export function reliabilityTone(r: ReliabilitySignal): FreshnessTone {
  const time = relativeTimeShort(r.lastConfirmedAt);
  switch (r.tier) {
    case "fresh":
      return { dotColor: "var(--sage)", label: `Confirmed ${time}`, labelKey: "fresh.lastChecked", labelVars: { time }, shouldPromote: true, urgentCall: false };
    case "recent":
      return { dotColor: "var(--mustard)", label: `Last checked ${time}`, labelKey: "fresh.lastChecked", labelVars: { time }, shouldPromote: true, urgentCall: false };
    case "stale":
      return { dotColor: "var(--stone)", label: "Not confirmed recently. Call first.", labelKey: "fresh.stale", shouldPromote: false, urgentCall: true };
    case "unknown":
    default:
      return { dotColor: "var(--stone)", label: "Unverified. Call first.", labelKey: "fresh.unknown", shouldPromote: false, urgentCall: true };
  }
}
