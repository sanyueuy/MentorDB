const API_BASE =
  process.env.MENTORDB_API_BASE_URL || process.env.NEXT_PUBLIC_MENTORDB_API_BASE_URL || "http://127.0.0.1:8000";

export type UniversityOption = {
  name: string;
  tiers: string[];
  metadata?: {
    name: string;
    is_985: boolean;
    is_211: boolean;
    is_double_first_class: boolean;
  } | null;
};

export type SchoolOption = {
  name: string;
  university: string;
};

export type FacultyCard = {
  slug: string;
  name: string;
  title?: string | null;
  school?: string;
  university?: string;
  tiers?: string[];
  homepage_url?: string | null;
  lab_url?: string | null;
  research_keywords?: string[];
  has_admissions?: boolean;
  source_count?: number;
};

export type SearchHit = {
  faculty_slug: string;
  faculty_name: string;
  score: number;
  section_type: string;
  section_label: string;
  snippet: string;
  source_url: string;
  metadata: Record<string, unknown>;
  faculty: FacultyCard;
};

export type SearchResponse = {
  query: string;
  filters: {
    university?: string | null;
    school?: string | null;
    universities?: string[];
    schools?: string[];
    tiers?: string[];
    keywords?: string[];
    require_admissions?: boolean;
    require_lab_url?: boolean;
  };
  cards_total: number;
  hits: SearchHit[];
};

export type FilterMetadata = {
  tiers: Array<{ key: string; label: string }>;
  universities: UniversityOption[];
  schools: SchoolOption[];
};

export type FacultySection = {
  section_type: string;
  title: string;
  content: string;
  source_url: string;
};

export type FacultySource = {
  url: string;
  label: string;
  source_type: string;
  status: string;
  is_external: boolean;
  final_url?: string | null;
  final_domain?: string | null;
  summary?: string | null;
};

export type ExternalPage = {
  url: string;
  title?: string | null;
  content_type: string;
  summary: string;
  metadata: Record<string, unknown>;
};

export type FacultyDetail = {
  slug: string;
  name: string;
  title?: string | null;
  school: string;
  university: string;
  tiers?: string[];
  homepage_url?: string | null;
  lab_url?: string | null;
  email?: string | null;
  phone?: string | null;
  research_keywords: string[];
  metadata: Record<string, unknown>;
  sections: FacultySection[];
  sources: FacultySource[];
  external_pages: ExternalPage[];
};

export async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchFilters(): Promise<FilterMetadata> {
  return apiFetch<FilterMetadata>("/api/meta/filters");
}

export async function fetchSearch(params: URLSearchParams): Promise<SearchResponse> {
  return apiFetch<SearchResponse>(`/api/search/faculty?${params.toString()}`);
}

export async function fetchFacultyDetail(slug: string): Promise<FacultyDetail> {
  return apiFetch<FacultyDetail>(`/api/faculty/${slug}`);
}
