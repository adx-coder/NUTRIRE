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

/** Same calendar-day slot that continues past midnight (e.g. 22:00–02:00). */
function isOvernightSlot(openMin: number, closeMin: number): boolean {
  return closeMin < openMin;
}

export function computeOpenStatus(org: EnrichedOrganization, now: Date): OpenStatus {
  const hours = org.ai?.parsedHours;
  if (!hours) return { state: "unknown", label: "Call for hours", labelKey: "status.callForHours" };

  if (hours.byAppointment && !hours.mon && !hours.tue && !hours.wed && !hours.thu && !hours.fri && !hours.sat && !hours.sun) {
    return { state: "unknown", label: "By appointment, call ahead", labelKey: "status.byAppointment" };
  }

  const allDaysHave24 = DAY_KEYS.every((d) => {
    const s = slotsForDay(hours, d);
    return s.length > 0 && s[0].start === "00:00" && (s[0].end === "23:59" || s[0].end === "24:00");
  });
  if (allDaysHave24) return { state: "open", label: "Open 24/7", labelKey: "status.open" };

  const todayKey = DAY_KEYS[now.getDay()];
  const currentMin = now.getHours() * 60 + now.getMinutes();
  const todaySlots = slotsForDay(hours, todayKey);
  const yesterdayKey = DAY_KEYS[(now.getDay() + 6) % 7];
  const yesterdaySlots = slotsForDay(hours, yesterdayKey);

  // Morning segment of an overnight window that started yesterday (e.g. Sat 22:00–Sun 02:00, now Sun 01:00)
  for (const slot of yesterdaySlots) {
    const open = parseMin(slot.start);
    const close = parseMin(slot.end);
    if (!isOvernightSlot(open, close)) continue;
    if (currentMin < close) {
      const time = fmtTime(slot.end);
      return { state: "open", label: `Open now - closes ${time}`, labelKey: "status.opensAt", labelVars: { time } };
    }
  }

  for (const slot of todaySlots) {
    const open = parseMin(slot.start);
    const close = parseMin(slot.end);

    if (isOvernightSlot(open, close)) {
      if (currentMin >= open) {
        const time = fmtTime(slot.end);
        return { state: "open", label: `Open now - closes ${time}`, labelKey: "status.opensAt", labelVars: { time } };
      }
      continue;
    }

    if (currentMin >= open && currentMin < close) {
      const time = fmtTime(slot.end);
      return { state: "open", label: `Open now - closes ${time}`, labelKey: "status.opensAt", labelVars: { time } };
    }
    if (currentMin < open) {
      const time = fmtTime(slot.start);
      return {
        state: "opens_today",
        label: `Opens today at ${time}${slot.note ? ` - ${slot.note}` : ""}`,
        labelKey: "status.opensAt",
        labelVars: { time },
      };
    }
  }

  for (let i = 1; i <= 7; i++) {
    const nextKey = DAY_KEYS[(now.getDay() + i) % 7];
    const nextSlots = slotsForDay(hours, nextKey);
    if (nextSlots.length > 0) {
      const dayLabel = i === 1 ? "Tomorrow" : DAY_NAMES[nextKey];
      const time = fmtTime(nextSlots[0].start);
      return {
        state: "opens_this_week",
        label: `${dayLabel} ${time}`,
        labelKey: "status.opensDay",
        labelVars: { day: dayLabel, time },
      };
    }
  }

  return { state: "closed_long", label: "Call for hours", labelKey: "status.callForHours" };
}
