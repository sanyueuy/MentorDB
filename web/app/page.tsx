import Link from "next/link";

import { fetchFilters, fetchSearch, type SearchHit } from "../lib/api";
import { highlightText, sectionTone, summarizeFilters, tierLabel } from "../lib/presentation";

type SearchParamValue = string | string[] | undefined;

function normalizeArray(value: SearchParamValue): string[] {
  if (!value) return [];
  return (Array.isArray(value) ? value : [value]).filter(Boolean);
}

function buildSearchParams(input: {
  q?: string;
  universities?: SearchParamValue;
  schools?: SearchParamValue;
  tiers?: SearchParamValue;
  require_admissions?: string;
  require_lab_url?: string;
  top_k?: string;
}) {
  const params = new URLSearchParams();
  params.set("q", input.q || "我想找做机器人的老师");
  for (const item of normalizeArray(input.universities)) params.append("universities", item);
  for (const item of normalizeArray(input.schools)) params.append("schools", item);
  for (const item of normalizeArray(input.tiers)) params.append("tiers", item);
  if (input.require_admissions === "on") params.set("require_admissions", "true");
  if (input.require_lab_url === "on") params.set("require_lab_url", "true");
  params.set("top_k", input.top_k || "10");
  return params;
}

function buildFocusKey(hit: SearchHit) {
  return `${hit.faculty_slug}::${hit.source_url}`;
}

function buildHref(search: URLSearchParams, updates: Record<string, string | string[] | null>) {
  const next = new URLSearchParams(search.toString());
  for (const [key, value] of Object.entries(updates)) {
    next.delete(key);
    if (value === null) continue;
    if (Array.isArray(value)) {
      value.forEach((item) => next.append(key, item));
    } else {
      next.set(key, value);
    }
  }
  return `/?${next.toString()}`;
}

function buildDetailHref(search: URLSearchParams, slug: string) {
  return `/faculty/${slug}?${search.toString()}`;
}

export default async function Home({
  searchParams,
}: {
  searchParams: {
    q?: string;
    universities?: string | string[];
    schools?: string | string[];
    tiers?: string | string[];
    require_admissions?: string;
    require_lab_url?: string;
    top_k?: string;
    focus?: string;
  };
}) {
  const selectedUniversities = normalizeArray(searchParams.universities);
  const selectedSchools = normalizeArray(searchParams.schools);
  const selectedTiers = normalizeArray(searchParams.tiers);
  const requestParams = buildSearchParams(searchParams);
  const [filtersMeta, data] = await Promise.all([fetchFilters(), fetchSearch(requestParams)]);

  const activeKey = searchParams.focus || (data.hits[0] ? buildFocusKey(data.hits[0]) : "");
  const active = data.hits.find((hit) => buildFocusKey(hit) === activeKey) || data.hits[0] || null;
  const filterSummary = summarizeFilters({
    universities: selectedUniversities,
    schools: selectedSchools,
    tiers: selectedTiers,
    require_admissions: searchParams.require_admissions === "on",
    require_lab_url: searchParams.require_lab_url === "on",
    top_k: Number(searchParams.top_k || "10"),
  });

  const visibleSchools = selectedUniversities.length
    ? filtersMeta.schools.filter((item) => selectedUniversities.includes(item.university))
    : filtersMeta.schools;

  return (
    <main className="page-shell">
      <div className="page-inner">
        <section className="hero hero-grid">
          <div>
            <div className="eyebrow">MentorDB Search Desk</div>
            <h1>多学校联合搜导师，结果带证据可追溯</h1>
            <p>现在可以同时勾选多个学校、多个学院和学校层级标签，用一套工作台完成跨校联合检索。</p>
          </div>
          <div className="hero-note">
            <div className="hero-note-label">产品版工作台</div>
            <div className="hero-note-value">支持多校 / 多院 / 层级标签</div>
            <div className="hero-note-meta">筛选语义：同类 OR，跨类 AND。适合普通用户直接在线使用。</div>
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
                placeholder="例如：我想找明确写了研究生招生信息的双一流老师"
              />
            </label>
          </div>

          <div className="multi-filter-layout">
            <section className="multi-filter-group">
              <div className="field-label">学校标签</div>
              <div className="chip-grid">
                {filtersMeta.tiers.map((tier) => (
                  <label className={`toggle-chip ${selectedTiers.includes(tier.key) ? "toggle-chip-active" : ""}`} key={tier.key}>
                    <input type="checkbox" name="tiers" value={tier.key} defaultChecked={selectedTiers.includes(tier.key)} />
                    <span>{tier.label}</span>
                  </label>
                ))}
              </div>
            </section>

            <section className="multi-filter-group">
              <div className="field-label">学校多选</div>
              <div className="chip-grid">
                {filtersMeta.universities.map((university) => (
                  <label
                    className={`toggle-chip ${selectedUniversities.includes(university.name) ? "toggle-chip-active" : ""}`}
                    key={university.name}
                  >
                    <input
                      type="checkbox"
                      name="universities"
                      value={university.name}
                      defaultChecked={selectedUniversities.includes(university.name)}
                    />
                    <span>{university.name}</span>
                    {university.tiers.map((tier) => (
                      <span className="tiny-tag" key={`${university.name}-${tier}`}>
                        {tierLabel(tier)}
                      </span>
                    ))}
                  </label>
                ))}
              </div>
            </section>

            <section className="multi-filter-group">
              <div className="field-label">学院多选</div>
              <div className="chip-grid">
                {visibleSchools.map((school) => (
                  <label
                    className={`toggle-chip ${selectedSchools.includes(school.name) ? "toggle-chip-active" : ""}`}
                    key={`${school.university}-${school.name}`}
                  >
                    <input type="checkbox" name="schools" value={school.name} defaultChecked={selectedSchools.includes(school.name)} />
                    <span>{school.name}</span>
                    <span className="tiny-tag">{school.university}</span>
                  </label>
                ))}
              </div>
            </section>
          </div>

          <div className="filters-grid compact-grid">
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
            <label className={`toggle-chip ${searchParams.require_admissions === "on" ? "toggle-chip-active" : ""}`}>
              <input type="checkbox" name="require_admissions" defaultChecked={searchParams.require_admissions === "on"} />
              <span>只看有招生说明</span>
            </label>
            <label className={`toggle-chip ${searchParams.require_lab_url === "on" ? "toggle-chip-active" : ""}`}>
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
                  <article className={`result-card tone-${tone}`} key={focusKey}>
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

                    <div className="tags">
                      {(hit.faculty.tiers || []).map((tier) => (
                        <span className="tag tag-tier" key={`${hit.faculty.slug}-${tier}`}>
                          {tierLabel(tier)}
                        </span>
                      ))}
                      {(hit.faculty.research_keywords || []).slice(0, 5).map((keyword) => (
                        <span className="tag" key={keyword}>
                          {keyword}
                        </span>
                      ))}
                    </div>

                    <p className="snippet">{highlightText(hit.snippet, data.query)}</p>

                    <div className="card-actions">
                      <Link className="text-link" href={buildHref(requestParams, { focus: buildFocusKey(hit) })}>
                        查看命中证据
                      </Link>
                      {hit.faculty.school ? (
                        <Link className="chip-link" href={buildHref(requestParams, { schools: [hit.faculty.school] })}>
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
                <p>可以换更宽松的关键词，去掉部分学校层级筛选，或者缩小学院范围再试。</p>
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
                    {(active.faculty.tiers || []).length ? (
                      <div>{(active.faculty.tiers || []).map((tier) => tierLabel(tier)).join(" / ")}</div>
                    ) : null}
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
