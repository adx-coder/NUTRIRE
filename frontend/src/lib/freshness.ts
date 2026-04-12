import type { ConfidenceSignal, ReliabilitySignal } from "@/types";
import { relativeTimeShort } from "./time";

export type FreshnessTone = {
  dotColor: string;
  label: string;
  shouldPromote: boolean;
  urgentCall: boolean;
};

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
  switch (r.tier) {
    case "fresh":
      return { dotColor: "var(--sage)", label: `Confirmed ${relativeTimeShort(r.lastConfirmedAt)}`, shouldPromote: true, urgentCall: false };
    case "recent":
      return { dotColor: "var(--mustard)", label: `Last checked ${relativeTimeShort(r.lastConfirmedAt)}`, shouldPromote: true, urgentCall: false };
    case "stale":
      return { dotColor: "var(--stone)", label: "Not confirmed recently — call first.", shouldPromote: false, urgentCall: true };
    case "unknown":
    default:
      return { dotColor: "var(--stone)", label: "Unverified — call first.", shouldPromote: false, urgentCall: true };
  }
}
