const API_BASE = process.env.NEXT_PUBLIC_MENTORDB_API_BASE_URL || "http://127.0.0.1:8000";

export async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { next: { revalidate: 0 } });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}
