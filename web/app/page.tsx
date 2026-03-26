import Link from "next/link";

import { apiFetch } from "../lib/api";

type SearchHit = {
  faculty_slug: string;
  faculty_name: string;
  score: number;
  section_type: string;
  snippet: string;
  source_url: string;
  faculty?: {
    school?: string;
    university?: string;
    title?: string;
    research_keywords?: string[];
  };
};

type SearchResponse = {
  hits: SearchHit[];
};

export default async function Home({
  searchParams
}: {
  searchParams: { q?: string; school?: string };
}) {
  const q = searchParams.q || "我想找做机器人的老师";
  const school = searchParams.school || "";
  const queryString = new URLSearchParams({ q, ...(school ? { school } : {}) }).toString();
  const data = await apiFetch<SearchResponse>(`/api/search/faculty?${queryString}`);
  const active = data.hits[0];

  return (
    <main className="page-shell">
      <div className="page-inner">
        <section className="hero">
          <div className="eyebrow">MentorDB</div>
          <h1>自然语言搜导师</h1>
          <p>输入研究方向、招生偏好或关键词，查看导师卡片、命中证据和来源链接。</p>
        </section>

        <form className="search-card" action="/">
          <input className="search-input" type="text" name="q" defaultValue={q} />
          <input className="select-input" type="text" name="school" defaultValue={school} placeholder="学院筛选，例如 控制科学与工程学院" />
        </form>

        <div className="grid">
          <section className="results">
            {data.hits.map((hit) => (
              <Link className="result-card" key={`${hit.faculty_slug}-${hit.source_url}`} href={`/faculty/${hit.faculty_slug}`}>
                <div className="eyebrow">{hit.section_type}</div>
                <h2 className="result-title">{hit.faculty_name}</h2>
                <div className="meta">
                  {hit.faculty?.university} / {hit.faculty?.school}
                  {hit.faculty?.title ? ` / ${hit.faculty.title}` : ""}
                </div>
                <p className="snippet">{hit.snippet}</p>
                <div className="tags">
                  {(hit.faculty?.research_keywords || []).slice(0, 4).map((keyword) => (
                    <span className="tag" key={keyword}>
                      {keyword}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </section>

          <aside className="panel">
            {active ? (
              <>
                <div className="eyebrow">Top Evidence</div>
                <h2 className="result-title">{active.faculty_name}</h2>
                <p className="snippet">{active.snippet}</p>
                <div className="source-item">
                  <strong>来源</strong>
                  <div className="meta">{active.source_url}</div>
                </div>
                <div className="source-item">
                  <strong>命中类型</strong>
                  <div className="meta">{active.section_type}</div>
                </div>
              </>
            ) : (
              <p className="meta">暂无命中结果。</p>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}
