/**
 * Async data loader — fetches real pipeline data from public/data/,
 * falls back to mock data if unavailable.
 *
 * Usage:
 *   const orgs = useOrgs();           // hook — returns orgs (mock initially, real after fetch)
 *   const gaps = useEquityGaps();     // hook — returns equity gap data
 */
import { useState, useEffect } from "react";
import type { EnrichedOrganization } from "@/types";
import { mockOrgs, mockUserLocation } from "./mock-orgs";

// ── Singleton caches ────────────────────────────────────────────────────────

let _orgs: EnrichedOrganization[] | null = null;
let _orgsPromise: Promise<EnrichedOrganization[]> | null = null;

let _gaps: EquityGapData | null = null;
let _gapsPromise: Promise<EquityGapData | null> | null = null;

let _access: AccessSummaryData | null = null;
let _accessPromise: Promise<AccessSummaryData | null> | null = null;

// ── Types for additional data ───────────────────────────────────────────────

export interface EquityGap {
  zip: string;
  label: string;
  centroidLat: number;
  centroidLon: number;
  population: number;
  needScore: number;
  supplyScore: number;
  gap: number;
  underservedPopulation: number;
  nearbyOrgCount: number;
  suggestedHost: { name: string; distance_km: number; has_hours: boolean } | null;
  why: string;
}

export interface EquityGapData {
  generatedAt: string;
  totalZipsAnalyzed: number;
  gaps: EquityGap[];
  summary: {
    highestGap: EquityGap | null;
    avgGap: number;
    totalUnderserved: number;
  };
}

export interface ZipAccess {
  zip: string;
  label: string;
  centroidLat: number;
  centroidLon: number;
  nearbyOrgCount: number;
  accessScore: number;
  dayAccess: Record<string, number>;
  languageAccess: Record<string, number>;
  dignityAccess: Record<string, number>;
  gaps: string[];
}

export interface AccessSummaryData {
  generatedAt: string;
  totalZips: number;
  zips: Record<string, ZipAccess>;
  summary: {
    avgAccessScore: number;
    zipsWithZeroOrgs: number;
    zipsWithWeekendGap: number;
    zipsWithNoLowFriction: number;
  };
}

// ── Fetch helpers ───────────────────────────────────────────────────────────

const BASE = import.meta.env.BASE_URL;

/** Replace em dashes with commas in user-facing text */
function cleanText(s: string | undefined | null): string {
  if (!s) return s as string;
  return s.replace(/\s*—\s*/g, ", ").replace(/^,\s*/, "");
}

function sanitizeOrg(org: EnrichedOrganization): EnrichedOrganization {
  if (org.ai) {
    org.ai.heroCopy = cleanText(org.ai.heroCopy) || undefined;
    org.ai.plainEligibility = cleanText(org.ai.plainEligibility) || "";
    org.ai.culturalNotes = cleanText(org.ai.culturalNotes) || undefined;
    if (org.ai.firstVisitGuide) {
      org.ai.firstVisitGuide = org.ai.firstVisitGuide.map((s) => cleanText(s) || s);
    }
  }
  return org;
}

async function fetchOrgs(): Promise<EnrichedOrganization[]> {
  try {
    const resp = await fetch(`${BASE}data/enriched-orgs.json`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (Array.isArray(data) && data.length > 0) {
      return data.map(sanitizeOrg);
    }
  } catch (e) {
    console.warn("[data] Failed to load real orgs, using mock:", e);
  }
  return mockOrgs;
}

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const resp = await fetch(`${BASE}data/${path}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

// ── Public API ──────────────────────────────────────────────────────────────

export function getOrgs(): Promise<EnrichedOrganization[]> {
  if (_orgs) return Promise.resolve(_orgs);
  if (!_orgsPromise) {
    _orgsPromise = fetchOrgs().then((data) => {
      _orgs = data;
      return data;
    });
  }
  return _orgsPromise;
}

export function getEquityGaps(): Promise<EquityGapData | null> {
  if (_gaps) return Promise.resolve(_gaps);
  if (!_gapsPromise) {
    _gapsPromise = fetchJson<EquityGapData>("equity-gaps.json").then((data) => {
      _gaps = data;
      return data;
    });
  }
  return _gapsPromise;
}

export function getAccessSummary(): Promise<AccessSummaryData | null> {
  if (_access) return Promise.resolve(_access);
  if (!_accessPromise) {
    _accessPromise = fetchJson<AccessSummaryData>("access-summary.json").then((data) => {
      _access = data;
      return data;
    });
  }
  return _accessPromise;
}

// ── React hooks ─────────────────────────────────────────────────────────────

export function useOrgs(): EnrichedOrganization[] {
  const [orgs, setOrgs] = useState<EnrichedOrganization[]>(_orgs ?? mockOrgs);

  useEffect(() => {
    if (_orgs) {
      setOrgs(_orgs);
      return;
    }
    getOrgs().then(setOrgs);
  }, []);

  return orgs;
}

export function useEquityGaps(): EquityGapData | null {
  const [data, setData] = useState<EquityGapData | null>(_gaps);
  useEffect(() => {
    getEquityGaps().then(setData);
  }, []);
  return data;
}

export function useAccessSummary(): AccessSummaryData | null {
  const [data, setData] = useState<AccessSummaryData | null>(_access);
  useEffect(() => {
    getAccessSummary().then(setData);
  }, []);
  return data;
}

export { mockUserLocation };
