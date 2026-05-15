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

function userKey(username: string | null, key: string): string {
  const ns = username ?? 'guest';
  return `${ns}.${key}`;
}

export function lsGetUser<T>(username: string | null, key: string, fallback: T): T {
  return lsGet(userKey(username, key), fallback);
}

export function lsSetUser<T>(username: string | null, key: string, value: T): void {
  lsSet(userKey(username, key), value);
}
