import type { ReactNode } from "react";

export function sectionTone(sectionType: string): string {
  return {
    admissions: "admissions",
    research: "research",
    self_intro: "self-intro",
    mentoring: "mentoring",
    achievements: "achievements",
    basic: "basic",
    contact: "contact",
    source_note: "source-note",
    other: "other",
  }[sectionType] || "other";
}

export function sourceKindLabel(sourceType: string): string {
  return {
    homepage: "主页",
    listing: "检索页",
    lab: "实验室",
    project: "项目",
    paper: "论文",
    other: "关联来源",
  }[sourceType] || "来源";
}

export function sourceStatusLabel(status: string): string {
  return {
    crawled: "已抓取",
    discovered: "已发现",
    redirected_internal: "跳回站内",
    reference: "参考入口",
  }[status] || status;
}

export function tokenizeQuery(query: string): string[] {
  const unique = new Set(
    query
      .split(/[\s,，。、“”"'；;：:（）()【】\[\]/]+/)
      .map((token) => token.trim())
      .filter((token) => token.length >= 2),
  );
  return [...unique].sort((a, b) => b.length - a.length);
}

export function highlightText(text: string, query: string): ReactNode {
  const tokens = tokenizeQuery(query);
  if (!tokens.length) return text;

  const escaped = tokens.map((token) => token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(pattern);

  return parts.map((part, index) => {
    const matched = tokens.some((token) => token.toLowerCase() === part.toLowerCase());
    if (!matched) return <span key={`${part}-${index}`}>{part}</span>;
    return (
      <mark className="inline-highlight" key={`${part}-${index}`}>
        {part}
      </mark>
    );
  });
}

export function summarizeFilters(filters: {
  universities?: string[];
  schools?: string[];
  tiers?: string[];
  require_admissions?: boolean;
  require_lab_url?: boolean;
  top_k?: number;
}): string[] {
  const parts: string[] = [];
  if (filters.universities?.length) parts.push(`学校 ${filters.universities.join(" / ")}`);
  if (filters.schools?.length) parts.push(`学院 ${filters.schools.join(" / ")}`);
  if (filters.tiers?.length) parts.push(`标签 ${filters.tiers.map((item) => tierLabel(item)).join(" / ")}`);
  if (filters.require_admissions) parts.push("仅看有招生说明");
  if (filters.require_lab_url) parts.push("仅看有实验室链接");
  if (filters.top_k) parts.push(`Top ${filters.top_k}`);
  return parts;
}

export function tierLabel(tier: string): string {
  return {
    "985": "985",
    "211": "211",
    double_first_class: "双一流",
  }[tier] || tier;
}
