-- The API connects as tracex_api: SELECT and INSERT on application tables, UPDATE only where a
-- row has a state, no DELETE except short-lived session data. users, user_coverage,
-- case_assignments and threshold_versions change only through apply_change(change_id).
-- The role itself is created by the bootstrap step (tracex_api.db.bootstrap_roles).

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO tracex_api;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO tracex_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tracex_api;

GRANT INSERT ON
    sessions, refresh_tokens, login_attempts, cases, upload_batches, documents, document_lines,
    entities, entity_mentions, match_runs, links, link_history, decision_outbox,
    link_cited_lines, stubs, access_requests, access_grants, grant_line_ranges,
    pending_changes, audit_log
TO tracex_api;

GRANT UPDATE ON
    sessions, refresh_tokens, links, access_requests, access_grants, upload_batches,
    match_runs, decision_outbox
TO tracex_api;
GRANT UPDATE (state, decider_id, decided_at, approved_hash) ON pending_changes TO tracex_api;

GRANT DELETE ON sessions, refresh_tokens, login_attempts, link_cited_lines TO tracex_api;

GRANT EXECUTE ON FUNCTION apply_change(uuid) TO tracex_api;
