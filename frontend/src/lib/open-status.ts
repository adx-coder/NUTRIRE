import type { EnrichedOrganization, OpenStatus, WeeklySchedule } from "@/types";

type DayKey = "sun" | "mon" | "tue" | "wed" | "thu" | "fri" | "sat";

const DAY_KEYS: DayKey[] = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const DAY_NAMES: Record<DayKey, string> = {
  sun: "Sunday",
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
};

function parseMin(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + (m || 0);
}

function fmtTime(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const ampm = h >= 12 ? "pm" : "am";
  const hr = h % 12 || 12;
  return m ? `${hr}:${String(m).padStart(2, "0")}${ampm}` : `${hr}${ampm}`;
}

function slotsForDay(hours: WeeklySchedule, day: DayKey) {
  return hours[day] ?? [];
}

export function computeOpenStatus(org: EnrichedOrganization, now: Date): OpenStatus {
  const hours = org.ai?.parsedHours;
  if (!hours) return { state: "unknown", label: "Call for hours" };

  if (hours.byAppointment && !hours.mon && !hours.tue && !hours.wed && !hours.thu && !hours.fri && !hours.sat && !hours.sun) {
    return { state: "unknown", label: "By appointment — call ahead" };
  }

  const allDaysHave24 = DAY_KEYS.every((d) => {
    const s = slotsForDay(hours, d);
    return s.length > 0 && s[0].start === "00:00" && (s[0].end === "23:59" || s[0].end === "24:00");
  });
  if (allDaysHave24) return { state: "open", label: "Open 24/7" };

  const todayKey = DAY_KEYS[now.getDay()];
  const currentMin = now.getHours() * 60 + now.getMinutes();
  const todaySlots = slotsForDay(hours, todayKey);

  for (const slot of todaySlots) {
    const open = parseMin(slot.start);
    const close = parseMin(slot.end);

    if (currentMin >= open && currentMin < close) {
      return { state: "open", label: `Open now · closes ${fmtTime(slot.end)}` };
    }
    if (currentMin < open) {
      return {
        state: "opens_today",
        label: `Opens today at ${fmtTime(slot.start)}${slot.note ? ` · ${slot.note}` : ""}`,
      };
    }
  }

  for (let i = 1; i <= 7; i++) {
    const nextKey = DAY_KEYS[(now.getDay() + i) % 7];
    const nextSlots = slotsForDay(hours, nextKey);
    if (nextSlots.length > 0) {
      const dayLabel = i === 1 ? "Tomorrow" : DAY_NAMES[nextKey];
      const note = nextSlots[0].note ? ` · ${nextSlots[0].note}` : "";
      return {
        state: "opens_this_week",
        label: `${dayLabel} ${fmtTime(nextSlots[0].start)}${note}`,
      };
    }
  }

  return { state: "closed_long", label: "Call for hours" };
}
