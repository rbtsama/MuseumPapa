const PREFIX = 'museumpass-ma';

export function lsGet<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`${PREFIX}.${key}`);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function lsSet<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`${PREFIX}.${key}`, JSON.stringify(value));
  } catch {
    // quota / privacy mode — swallow
  }
}

export function lsRemove(key: string): void {
  try {
    localStorage.removeItem(`${PREFIX}.${key}`);
  } catch {
    // swallow
  }
}
