/**
 * Lightweight analytics — tracks anonymized search/click events.
 *
 * Stores events in localStorage and optionally sends to the analytics server
 * (scripts/analytics_server.py) when running locally.
 *
 * No PII is collected. Only ZIP codes, filter names, and org IDs are logged.
 */

const STORAGE_KEY = "nutrire_analytics";
const ANALYTICS_URL = "http://localhost:3001/api/analytics";

interface AnalyticsEvent {
  event: "search" | "click" | "filter" | "page_view";
  ts: string;
  [key: string]: unknown;
}

function getEvents(): AnalyticsEvent[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveEvent(evt: AnalyticsEvent) {
  const events = getEvents();
  events.push(evt);
  // Keep last 500 events
  const trimmed = events.slice(-500);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));

  // Fire-and-forget to analytics server (if running)
  try {
    fetch(ANALYTICS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(evt),
    }).catch(() => {});
  } catch {
    // Server not running — that's fine, events are in localStorage
  }
}

/** Track a ZIP code search */
export function trackSearch(zip: string, filters?: string[]) {
  saveEvent({
    event: "search",
    ts: new Date().toISOString(),
    zip,
    filters: filters || [],
  });
}

/** Track an org card click */
export function trackOrgClick(orgId: string, orgName: string, fromPage: string) {
  saveEvent({
    event: "click",
    ts: new Date().toISOString(),
    orgId,
    orgName: orgName.slice(0, 50),
    fromPage,
  });
}

/** Track a filter toggle */
export function trackFilter(filterName: string, value: boolean) {
  saveEvent({
    event: "filter",
    ts: new Date().toISOString(),
    filter: filterName,
    value,
  });
}

/** Track a page view */
export function trackPageView(page: string) {
  saveEvent({
    event: "page_view",
    ts: new Date().toISOString(),
    page,
  });
}

/** Get analytics summary for display */
export function getAnalyticsSummary() {
  const events = getEvents();
  const searches = events.filter((e) => e.event === "search");
  const clicks = events.filter((e) => e.event === "click");

  const zipCounts: Record<string, number> = {};
  for (const s of searches) {
    const zip = s.zip as string;
    if (zip) zipCounts[zip] = (zipCounts[zip] || 0) + 1;
  }

  const orgCounts: Record<string, number> = {};
  for (const c of clicks) {
    const id = c.orgId as string;
    if (id) orgCounts[id] = (orgCounts[id] || 0) + 1;
  }

  return {
    totalEvents: events.length,
    searches: searches.length,
    clicks: clicks.length,
    topZips: Object.entries(zipCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10),
    topOrgs: Object.entries(orgCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10),
  };
}
