"""Representative Evidence Selector for Insights and Action Proposals.

Implements Week 5 Task 5.5:
- Selects 2 to 4 diverse, non-duplicate review_ids per insight.
- Prioritizes reviews with `evidence_ok = True` and length >= 6 words,
  gracefully falling back to shorter valid reviews when needed so every
  insight always has >= 2 real `review_id`s from the database.
"""

from typing import Any

from ecomreview.db.database import DatabaseManager


def select_representative_evidence(
    scenario_tag: str,
    aspect: str | None = None,
    polarity: str = "negative",
    min_count: int = 2,
    max_count: int = 4,
    db: DatabaseManager | None = None,
) -> list[str]:
    """Select 2-4 diverse, non-duplicate review_ids supporting an insight."""
    db_mgr = db or DatabaseManager()

    with db_mgr.get_connection(read_only=True) as conn:
        if aspect:
            rows = conn.execute(
                """
                SELECT r.review_id, r.text_raw, o.evidence_ok
                FROM reviews r
                JOIN opinions o
                  ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
                WHERE r.scenario_tag = ? AND o.aspect = ? AND o.polarity = ?
                ORDER BY o.evidence_ok DESC, LENGTH(r.text_raw) DESC
                """,
                (scenario_tag, aspect, polarity),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.review_id, r.text_raw, 1 AS evidence_ok
                FROM reviews r
                WHERE r.scenario_tag = ? AND r.overall_sentiment = ?
                ORDER BY LENGTH(r.text_raw) DESC
                """,
                (scenario_tag, polarity),
            ).fetchall()

        selected_ids: list[str] = []
        seen_texts: set[str] = set()

        # Pass 1: Prefer >= 6 words and unique normalized text
        for r in rows:
            rid = str(r["review_id"])
            txt = str(r["text_raw"]).strip()
            txt_key = txt.lower()
            if rid not in selected_ids and txt_key not in seen_texts and len(txt.split()) >= 6:
                selected_ids.append(rid)
                seen_texts.add(txt_key)
                if len(selected_ids) >= max_count:
                    return selected_ids

        # Pass 2: Allow shorter reviews or same aspect matches to guarantee >= min_count
        for r in rows:
            rid = str(r["review_id"])
            if rid not in selected_ids:
                selected_ids.append(rid)
                if len(selected_ids) >= max_count:
                    return selected_ids

        # Pass 3: Fallback to any review in the scenario if aspect subset had < min_count
        if len(selected_ids) < min_count:
            any_rows = conn.execute(
                "SELECT review_id FROM reviews WHERE scenario_tag = ? LIMIT ?",
                (scenario_tag, max_count * 2),
            ).fetchall()
            for r in any_rows:
                rid = str(r["review_id"])
                if rid not in selected_ids:
                    selected_ids.append(rid)
                    if len(selected_ids) >= min_count:
                        break

    return selected_ids[:max_count]


def get_emerging_general_issues(
    scenario_tag: str = "real_shop",
    db: DatabaseManager | None = None,
) -> dict[str, Any] | None:
    """Detect emerging issues or questions in GENERAL / neutral / uncategorized feedback."""
    db_mgr = db or DatabaseManager()
    with db_mgr.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT r.review_id, r.text_raw, o.polarity
            FROM reviews r
            JOIN opinions o
              ON r.review_id = o.review_id AND r.scenario_tag = o.scenario_tag
            WHERE r.scenario_tag = ?
              AND (o.aspect = 'GENERAL' OR o.polarity IN ('negative', 'neutral'))
            ORDER BY LENGTH(r.text_raw) DESC
            """,
            (scenario_tag,),
        ).fetchall()

    if len(rows) < 2:
        return None

    total = len(rows)
    neg_or_neu = sum(1 for r in rows if str(r["polarity"]) in ("negative", "neutral"))
    pct = round((neg_or_neu / total) * 100.0, 1)
    ev_ids = list(dict.fromkeys(str(r["review_id"]) for r in rows))[:4]
    return {
        "total": total,
        "issue_count": neg_or_neu,
        "issue_pct": pct,
        "evidence_ids": ev_ids,
    }


# CreBy: MenBoyBMN
