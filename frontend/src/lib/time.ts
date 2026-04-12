import { formatDistanceToNowStrict, format, differenceInMinutes, differenceInDays, isToday, isTomorrow } from "date-fns";

/** "2 hours ago" / "1 day ago" — short form for confidence strings. */
export function relativeTimeShort(iso: string): string {
  const d = new Date(iso);
  return formatDistanceToNowStrict(d, { addSuffix: true });
}

/** "Tomorrow 10:00 AM" / "Today 5:00 PM" / "Saturday 10:00 AM" / "April 18, 10:00 AM" */
export function humanTimeWindow(startIso: string, endIso: string, now = new Date()): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const dayLabel = isToday(start)
    ? "Today"
    : isTomorrow(start)
    ? "Tomorrow"
    : differenceInDays(start, now) < 7
    ? format(start, "EEEE")
    : format(start, "MMMM d");
  const startTime = format(start, "h:mm a");
  const endTime = format(end, "h:mm a");
  return `${dayLabel} ${startTime}–${endTime}`;
}

/** "Tomorrow" / "Today" / "Saturday" / "April 18" — eyebrow only. */
export function eyebrowDay(startIso: string, now = new Date()): string {
  const start = new Date(startIso);
  if (isToday(start)) return "Today";
  if (isTomorrow(start)) return "Tomorrow";
  if (differenceInDays(start, now) < 7) return format(start, "EEEE");
  return format(start, "MMM d");
}

/** "10:00 AM — 1:00 PM" */
export function timeRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  return `${format(start, "h:mm a")} — ${format(end, "h:mm a")}`;
}

/** Minutes from now until event starts. Negative means event started. */
export function minutesUntil(iso: string, now = new Date()): number {
  return differenceInMinutes(new Date(iso), now);
}
