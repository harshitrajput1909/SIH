export async function getJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(path, {
      method: 'GET',
      cache: 'no-store',
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}
