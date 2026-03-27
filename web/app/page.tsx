import Link from "next/link";

import { fetchFilters, fetchSearch, type SearchHit } from "../lib/api";
import { highlightText, sectionTone, summarizeFilters } from "../lib/presentation";

function buildSearchParams(input: {
  q?: string;
  university?: string;
  school?: string;
  require_admissions?: string;
  require_lab_url?: string;
  top_k?: string;
}) {
  const params = new URLSearchParams();
  params.set("q", input.q || "我想找做机器人的老师");
  if (input.university) params.set("university", input.university);
  if (input.school) params.set("school", input.school);
  if (input.require_admissions === "on") params.set("require_admissions", "true");
  if (input.require_lab_url === "on") params.set("require_lab_url", "true");
  params.set("top_k", input.top_k || "10");
  return params;
}

function buildFocusKey(hit: SearchHit) {
  return `${hit.faculty_slug}::${hit.source_url}`;
}

function buildFocusHref(search: URLSearchParams, focus: string) {
  const next = new URLSearchParams(search.toString());
  next.set("focus", focus);
  return `/?${next.toString()}`;
}

function buildDetailHref(search: URLSearchParams, slug: string) {
  const next = new URLSearchParams(search.toString());
  return `/faculty/${slug}?${next.toString()}`;
}

export default async function Home({
  searchParams,
}: {
  searchParams: {
    q?: string;
    university?: string;
    school?: string;
    require_admissions?: string;
    require_lab_url?: string;
    top_k?: string;
    focus?: string;
  };
}) {
  const requestParams = buildSearchParams(searchParams);
  const [filtersMeta, data] = await Promise.all([fetchFilters(), fetchSearch(requestParams)]);

  const activeKey = searchParams.focus || (data.hits[0] ? buildFocusKey(data.hits[0]) : "");
  const active = data.hits.find((hit) => buildFocusKey(hit) === activeKey) || data.hits[0] || null;
  const filterSummary = summarizeFilters({
    university: searchParams.university,
    school: searchParams.school,
    require_admissions: searchParams.require_admissions === "on",
    require_lab_url: searchParams.require_lab_url === "on",
    top_k: Number(searchParams.top_k || "10"),
  });

  return (
    <main className="page-shell">
      <div className="page-inner">
        <section className="hero hero-grid">
          <div>
            <div className="eyebrow">MentorDB Search Desk</div>
            <h1>自然语言搜导师，证据化做判断</h1>
            <p>
              用一句自然语言描述方向、招生偏好或背景要求，快速看到老师卡片、命中证据和原始来源。
            </p>
          </div>
          <div className="hero-note">
            <div className="hero-note-label">当前数据库</div>
            <div className="hero-note-value">浙江大学三学院深抓库</div>
            <div className="hero-note-meta">控制、计算机、软件，共 435 位老师</div>
          </div>
        </section>

        <form className="search-card" action="/">
          <div className="search-row">
            <label className="field">
              <span className="field-label">自然语言查询</span>
              <input
                className="search-input"
                type="text"
                name="q"
                defaultValue={searchParams.q || "我想找做机器人的老师"}
                placeholder="例如：明确写了研究生招生信息的老师"
              />
            </label>
          </div>

          <div className="filters-grid">
            <label className="field">
              <span className="field-label">学校</span>
              <select className="select-input" name="university" defaultValue={searchParams.university || ""}>
                <option value="">全部学校</option>
                {filtersMeta.universities.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field-label">学院</span>
              <select className="select-input" name="school" defaultValue={searchParams.school || ""}>
                <option value="">全部学院</option>
                {filtersMeta.schools.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className="field field-small">
              <span className="field-label">返回数量</span>
              <select className="select-input" name="top_k" defaultValue={searchParams.top_k || "10"}>
                {[5, 10, 15, 20].map((value) => (
                  <option key={value} value={value}>
                    Top {value}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="toggle-row">
            <label className="toggle-chip">
              <input type="checkbox" name="require_admissions" defaultChecked={searchParams.require_admissions === "on"} />
              <span>只看有招生说明</span>
            </label>
            <label className="toggle-chip">
              <input type="checkbox" name="require_lab_url" defaultChecked={searchParams.require_lab_url === "on"} />
              <span>只看有实验室链接</span>
            </label>
            <button className="submit-button" type="submit">
              开始检索
            </button>
          </div>
        </form>

        <div className="results-toolbar">
          <div>
            <div className="toolbar-title">检索结果</div>
            <div className="toolbar-meta">当前返回 {data.cards_total} 条命中证据</div>
          </div>
          <div className="filter-summary">
            {filterSummary.length ? (
              filterSummary.map((item) => (
                <span className="summary-chip" key={item}>
                  {item}
                </span>
              ))
            ) : (
              <span className="summary-chip summary-chip-muted">未加筛选</span>
            )}
          </div>
        </div>

        <div className="workspace-grid">
          <section className="results">
            {data.hits.length ? (
              data.hits.map((hit) => {
                const tone = sectionTone(hit.section_type);
                const focusKey = buildFocusKey(hit);
                return (
                  <article className={`result-card tone-${tone}`} key={`${focusKey}`}>
                    <div className="result-head">
                      <div>
                        <div className="eyebrow">{hit.section_label}</div>
                        <h2 className="result-title">{hit.faculty_name}</h2>
                      </div>
                      <div className="score-pill">分数 {hit.score.toFixed(3)}</div>
                    </div>

                    <div className="meta">
                      {hit.faculty.university} / {hit.faculty.school}
                      {hit.faculty.title ? ` / ${hit.faculty.title}` : ""}
                    </div>

                    <p className="snippet">{highlightText(hit.snippet, data.query)}</p>

                    <div className="tags">
                      {(hit.faculty.research_keywords || []).slice(0, 5).map((keyword) => (
                        <span className="tag" key={keyword}>
                          {keyword}
                        </span>
                      ))}
                    </div>

                    <div className="card-actions">
                      <Link className="text-link" href={buildFocusHref(requestParams, focusKey)}>
                        查看命中证据
                      </Link>
                      {hit.faculty.school ? (
                        <Link
                          className="chip-link"
                          href={`/?${new URLSearchParams({
                            ...Object.fromEntries(requestParams.entries()),
                            school: hit.faculty.school,
                          }).toString()}`}
                        >
                          收窄到 {hit.faculty.school}
                        </Link>
                      ) : null}
                      <Link className="primary-link" href={buildDetailHref(requestParams, hit.faculty_slug)}>
                        查看导师档案
                      </Link>
                    </div>
                  </article>
                );
              })
            ) : (
              <div className="empty-state">
                <div className="empty-title">没有找到匹配结果</div>
                <p>可以试试更宽松的关键词，或去掉“招生说明 / 实验室链接”筛选。</p>
              </div>
            )}
          </section>

          <aside className="panel">
            {active ? (
              <>
                <div className="panel-kicker">当前证据</div>
                <h2 className="panel-title">{active.faculty_name}</h2>
                <div className={`panel-badge tone-${sectionTone(active.section_type)}`}>{active.section_label}</div>
                <p className="panel-snippet">{highlightText(active.snippet, data.query)}</p>

                <div className="panel-group">
                  <div className="panel-group-title">导师卡片</div>
                  <div className="panel-info-list">
                    <div>{active.faculty.university}</div>
                    <div>{active.faculty.school}</div>
                    {active.faculty.title ? <div>{active.faculty.title}</div> : null}
                  </div>
                </div>

                <div className="panel-group">
                  <div className="panel-group-title">来源</div>
                  <a className="source-link" href={active.source_url} target="_blank" rel="noreferrer">
                    打开原始来源
                  </a>
                </div>

                <div className="panel-group">
                  <div className="panel-group-title">快速跳转</div>
                  <Link className="primary-link block-link" href={buildDetailHref(requestParams, active.faculty_slug)}>
                    打开完整导师档案
                  </Link>
                  {active.faculty.homepage_url ? (
                    <a className="secondary-link block-link" href={active.faculty.homepage_url} target="_blank" rel="noreferrer">
                      打开教师主页
                    </a>
                  ) : null}
                </div>
              </>
            ) : (
              <div className="empty-state compact">
                <div className="empty-title">暂无可展示证据</div>
                <p>先输入查询，再从结果中挑一位老师查看命中依据。</p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}
