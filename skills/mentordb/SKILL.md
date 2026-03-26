---
name: mentordb
description: Use MentorDB to search faculty profiles, admissions notes, research directions, and source-backed advisor recommendations through the local mentor-index CLI.
metadata:
  short-description: Search MentorDB with source-backed faculty retrieval
---

# MentorDB

Use this skill when the user wants to find advisors by natural language, compare mentors, or ask which teachers explicitly mention admissions preferences, research areas, or team details.

This skill relies on a local CLI instead of re-implementing retrieval logic.

## Requirements

- Binary: `mentor-index`
- Environment variable: `MENTOR_INDEX_DATABASE_URL`

## Workflow

1. Rewrite the user request into a concise retrieval query.
2. Run:
   `mentor-index search faculty "<query>" --json`
3. Read the returned hits and prioritize `admissions` and `research` evidence when the user is asking about recruiting, fit, or direction.
4. Summarize only from returned evidence.
5. Include the source URL for every recommendation or claim.

## Guidance

- If the user asks for “明确写了招研究生的老师”, prefer hits where `section_type=admissions`.
- If the user asks for a topic such as robotics, vision, medical AI, or systems, prefer `research` hits over `basic`.
- If the query is broad, give a short ranked list and explain why each teacher matched.
- If the result quality looks weak, narrow with school filters or reformulate the query and run another search.
- Do not invent personal evaluations that are not present in the evidence.
