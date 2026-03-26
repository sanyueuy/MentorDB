import Link from "next/link";

import { apiFetch } from "../../../lib/api";

type DetailResponse = {
  name: string;
  school: string;
  university: string;
  title?: string;
  research_keywords: string[];
  sections: Array<{ title: string; content: string; source_url: string }>;
  sources: Array<{ url: string; label: string; status: string; summary?: string | null }>;
  external_pages: Array<{ url: string; title?: string | null; summary: string }>;
};

export default async function FacultyDetail({ params }: { params: { slug: string } }) {
  const detail = await apiFetch<DetailResponse>(`/api/faculty/${params.slug}`);

  return (
    <main className="page-shell">
      <div className="page-inner">
        <Link className="eyebrow" href="/">
          Back to Search
        </Link>
        <section className="hero" style={{ marginTop: 18 }}>
          <h1>{detail.name}</h1>
          <p>
            {detail.university} / {detail.school}
            {detail.title ? ` / ${detail.title}` : ""}
          </p>
          <div className="tags">
            {detail.research_keywords.map((keyword) => (
              <span className="tag" key={keyword}>
                {keyword}
              </span>
            ))}
          </div>
        </section>

        <div className="grid">
          <section className="results">
            {detail.sections.map((section) => (
              <article className="result-card" key={`${section.title}-${section.source_url}`}>
                <div className="eyebrow">{section.title}</div>
                <p className="snippet">{section.content}</p>
                <div className="meta">{section.source_url}</div>
              </article>
            ))}
          </section>

          <aside className="panel">
            <div className="eyebrow">外链与来源</div>
            {detail.sources.map((source) => (
              <div className="source-item" key={source.url}>
                <strong>{source.label}</strong>
                <div className="meta">{source.status}</div>
                <div className="meta">{source.url}</div>
                {source.summary ? <p className="snippet">{source.summary}</p> : null}
              </div>
            ))}
            {detail.external_pages.length ? (
              <>
                <div className="eyebrow" style={{ marginTop: 18 }}>外链正文摘要</div>
                {detail.external_pages.map((page) => (
                  <div className="source-item" key={page.url}>
                    <strong>{page.title || "外链页面"}</strong>
                    <p className="snippet">{page.summary}</p>
                  </div>
                ))}
              </>
            ) : null}
          </aside>
        </div>
      </div>
    </main>
  );
}
