function pad(n: number): string { return n < 10 ? `0${n}` : String(n); }

function toIso(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function next7Days(startIso: string): string[] {
  const start = new Date(`${startIso}T00:00:00`);
  const out: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    out.push(toIso(d));
  }
  return out;
}
