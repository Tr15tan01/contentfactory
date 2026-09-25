/**
 * Time-zone helpers without a date library. Schedules are stored as UTC instants but shown
 * and edited in the workspace's time zone (not the browser's).
 */

function parts(date: Date, timeZone: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const p of new Intl.DateTimeFormat("en-US", {
    timeZone, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(date)) {
    if (p.type !== "literal") out[p.type] = Number(p.value);
  }
  return out;
}

/** Wall-clock parts of an instant in a zone. */
export function zonedParts(date: Date, timeZone: string) {
  const p = parts(date, timeZone);
  return { year: p.year!, month: p.month!, day: p.day!, hour: p.hour! % 24, minute: p.minute! };
}

/** The UTC instant for a wall-clock time in a zone (handles DST by iterating on the offset). */
export function zonedToUtc(year: number, month: number, day: number, hour: number, minute: number, timeZone: string): Date {
  const target = Date.UTC(year, month - 1, day, hour, minute);
  let guess = target;
  for (let i = 0; i < 3; i++) {
    const p = parts(new Date(guess), timeZone);
    const asUtc = Date.UTC(p.year!, p.month! - 1, p.day!, p.hour! % 24, p.minute!);
    guess += target - asUtc;
  }
  return new Date(guess);
}

export function dayKey(date: Date, timeZone: string): string {
  const p = zonedParts(date, timeZone);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}

/** "2026-09-24T18:00" in the zone, for <input type="datetime-local">. */
export function toLocalInput(iso: string, timeZone: string): string {
  const p = zonedParts(new Date(iso), timeZone);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}T${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
}

export function fromLocalInput(value: string, timeZone: string): string {
  const [d, t] = value.split("T");
  const [y, m, day] = d!.split("-").map(Number);
  const [h, mi] = (t ?? "10:00").split(":").map(Number);
  return zonedToUtc(y!, m!, day!, h!, mi!, timeZone).toISOString();
}

export function formatInZone(iso: string, timeZone: string, opts: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat("en-US", { ...opts, timeZone }).format(new Date(iso));
}
