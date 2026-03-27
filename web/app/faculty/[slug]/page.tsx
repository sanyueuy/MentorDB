import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchFacultyDetail } from "../../../lib/api";
import { highlightText, sectionTone, sourceKindLabel, sourceStatusLabel } from "../../../lib/presentation";

function groupSections(sections: Array<{ section_type: string; title: string; content: string; source_url: string }>) {
  const preferredOrder = [
    "basic",
    "admissions",
    "research",
    "self_intro",
    "mentoring",
    "achievements",
    "contact",
    "source_note",
    "other",
  ];
  const grouped = new Map<string, typeof sections>();
  for (const section of sections) {
    if (!grouped.has(section.section_type)) grouped.set(section.section_type, []);
    grouped.get(section.section_type)!.push(section);
  }
  return preferredOrder
    .filter((key) => grouped.has(key))
    .map((key) => ({ sectionType: key, items: grouped.get(key)! }));
}

function backHref(searchParams: Record<string, string | string[] | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (typeof value === "string" && value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `/?${query}` : "/";
}

export default async function FacultyDetailPage({
  params,
  searchParams,
}: {
  params: { slug: string };
  searchParams: Record<string, string | string[] | undefined>;
}) {
  let detail;
  try {
    detail = await fetchFacultyDetail(params.slug);
  } catch {
    notFound();
  }

  const sectionGroups = groupSections(detail.sections);

  return (
    <main className="page-shell detail-shell">
      <div className="page-inner detail-inner">
        <div className="detail-topbar">
          <Link className="text-link" href={backHref(searchParams)}>
            返回搜索工作台
          </Link>
          {detail.homepage_url ? (
            <a className="secondary-link" href={detail.homepage_url} target="_blank" rel="noreferrer">
              打开教师主页
            </a>
          ) : null}
        </div>

        <section className="detail-hero">
          <div>
            <div className="eyebrow">Mentor Archive</div>
            <h1>{detail.name}</h1>
            <p className="hero-subtitle">
              {detail.university} / {detail.school}
              {detail.title ? ` / ${detail.title}` : ""}
            </p>
          </div>
          <div className="hero-sidecard">
            <div className="hero-sidecard-label">快速判断</div>
            <ul className="plain-list">
              <li>研究关键词：{detail.research_keywords.join("、") || "未公开"}</li>
              <li>邮箱：{detail.email || "未公开"}</li>
              <li>电话：{detail.phone || "未公开"}</li>
              <li>实验室链接：{detail.lab_url ? "已公开" : "未公开"}</li>
            </ul>
          </div>
        </section>

        <div className="detail-layout">
          <section className="detail-main">
            <article className="detail-card tone-basic">
              <div className="detail-card-head">
                <div className="section-badge">基础信息</div>
              </div>
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label">学校</span>
                  <span>{detail.university}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">学院</span>
                  <span>{detail.school}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">职称</span>
                  <span>{detail.title || "未公开"}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">研究关键词</span>
                  <span>{detail.research_keywords.join("、") || "未公开"}</span>
                </div>
              </div>
            </article>

            {sectionGroups.map((group) => (
              <article className={`detail-card tone-${sectionTone(group.sectionType)}`} key={group.sectionType}>
                <div className="detail-card-head">
                  <div className="section-badge">{group.items[0].title}</div>
                  <div className="section-count">{group.items.length} 条证据</div>
                </div>
                <div className="detail-sections">
                  {group.items.map((section) => (
                    <section className="detail-section" key={`${section.title}-${section.source_url}`}>
                      {group.items.length > 1 ? <h3>{section.title}</h3> : null}
                      <p className="section-content">{highlightText(section.content, section.title)}</p>
                      <a className="source-link" href={section.source_url} target="_blank" rel="noreferrer">
                        查看来源
                      </a>
                    </section>
                  ))}
                </div>
              </article>
            ))}
          </section>

          <aside className="detail-side">
            <section className="panel">
              <div className="panel-kicker">来源总览</div>
              <h2 className="panel-title">可追溯来源</h2>
              <div className="source-stack">
                {detail.sources.map((source) => (
                  <div className="source-card" key={`${source.url}-${source.label}`}>
                    <div className="source-card-top">
                      <span className="source-kind">{sourceKindLabel(source.source_type)}</span>
                      <span className={`status-pill status-${source.status}`}>{sourceStatusLabel(source.status)}</span>
                    </div>
                    <div className="source-name">{source.label}</div>
                    <a className="source-link" href={source.final_url || source.url} target="_blank" rel="noreferrer">
                      打开来源
                    </a>
                    {source.summary ? <p className="source-summary">{source.summary}</p> : null}
                  </div>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-kicker">外链摘要</div>
              <h2 className="panel-title">实验室 / 项目 / 代码</h2>
              {detail.external_pages.length ? (
                <div className="source-stack">
                  {detail.external_pages.map((page) => (
                    <div className="source-card" key={page.url}>
                      <div className="source-name">{page.title || "外部页面"}</div>
                      <a className="source-link" href={page.url} target="_blank" rel="noreferrer">
                        {page.url}
                      </a>
                      <p className="source-summary">{page.summary}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact">
                  <div className="empty-title">暂无外链正文</div>
                  <p>这位老师当前没有已抓取的实验室、项目或代码外链摘要。</p>
                </div>
              )}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
