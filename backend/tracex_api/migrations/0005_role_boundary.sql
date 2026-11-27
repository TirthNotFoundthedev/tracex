-- A role change across the SENIOR boundary carries what the new role needs: coverage for
-- SENIOR, a district for a district role. The users CHECK allows a district only for district
-- roles, so apply_change sets or clears it with the role instead of failing.

CREATE OR REPLACE FUNCTION apply_change(change uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    c pending_changes%ROWTYPE;
    new_user uuid;
    cov jsonb;
    next_version integer;
BEGIN
    SELECT * INTO c FROM pending_changes WHERE id = change FOR UPDATE;
    IF NOT FOUND OR c.state <> 'APPROVED' OR c.applied
       OR c.approved_hash IS DISTINCT FROM c.change_hash THEN
        RAISE EXCEPTION 'change % is not approved for application', change;
    END IF;
    IF c.kind = 'USER_CREATE' THEN
        INSERT INTO users (username, display_name, role, district_id)
        VALUES (
            c.new_value ->> 'username', c.new_value ->> 'display_name', c.new_value ->> 'role',
            NULLIF(c.new_value ->> 'district_id', '')::uuid
        ) RETURNING id INTO new_user;
        FOR cov IN SELECT * FROM jsonb_array_elements(coalesce(c.new_value -> 'coverage_rows', '[]'::jsonb)) LOOP
            INSERT INTO user_coverage (user_id, state_id, district_id, all_states)
            VALUES (
                new_user, NULLIF(cov ->> 'state_id', '')::uuid,
                NULLIF(cov ->> 'district_id', '')::uuid, coalesce((cov ->> 'all_states')::boolean, false)
            );
        END LOOP;
    ELSIF c.kind = 'USER_ENABLE' THEN
        UPDATE users SET active = true, authz_version = authz_version + 1 WHERE id = c.subject_user_id;
    ELSIF c.kind = 'USER_DISABLE' THEN
        UPDATE users SET active = false, authz_version = authz_version + 1 WHERE id = c.subject_user_id;
    ELSIF c.kind = 'USER_ROLE' THEN
        -- A district role keeps or takes a district; SENIOR and ADMIN have none (users CHECK).
        UPDATE users SET role = c.new_value ->> 'role',
            district_id = CASE WHEN c.new_value ->> 'role' IN ('JUNIOR', 'INVESTIGATOR', 'SUPERVISOR')
                THEN coalesce(NULLIF(c.new_value ->> 'district_id', '')::uuid, district_id)
                ELSE NULL END,
            authz_version = authz_version + 1
        WHERE id = c.subject_user_id;
        DELETE FROM user_coverage WHERE user_id = c.subject_user_id;
        FOR cov IN SELECT * FROM jsonb_array_elements(coalesce(c.new_value -> 'coverage_rows', '[]'::jsonb)) LOOP
            INSERT INTO user_coverage (user_id, state_id, district_id, all_states)
            VALUES (
                c.subject_user_id, NULLIF(cov ->> 'state_id', '')::uuid,
                NULLIF(cov ->> 'district_id', '')::uuid, coalesce((cov ->> 'all_states')::boolean, false)
            );
        END LOOP;
    ELSIF c.kind = 'USER_JURISDICTION' THEN
        UPDATE users SET district_id = NULLIF(c.new_value ->> 'district_id', '')::uuid,
            authz_version = authz_version + 1
        WHERE id = c.subject_user_id;
        DELETE FROM user_coverage WHERE user_id = c.subject_user_id;
        FOR cov IN SELECT * FROM jsonb_array_elements(coalesce(c.new_value -> 'coverage_rows', '[]'::jsonb)) LOOP
            INSERT INTO user_coverage (user_id, state_id, district_id, all_states)
            VALUES (
                c.subject_user_id, NULLIF(cov ->> 'state_id', '')::uuid,
                NULLIF(cov ->> 'district_id', '')::uuid, coalesce((cov ->> 'all_states')::boolean, false)
            );
        END LOOP;
    ELSIF c.kind = 'ASSIGNMENT_ADD' THEN
        INSERT INTO case_assignments (case_id, user_id, active)
        VALUES ((c.new_value ->> 'case_id')::uuid, c.subject_user_id, true)
        ON CONFLICT (case_id, user_id) DO UPDATE SET active = true;
        UPDATE users SET authz_version = authz_version + 1 WHERE id = c.subject_user_id;
    ELSIF c.kind = 'ASSIGNMENT_REMOVE' THEN
        UPDATE case_assignments SET active = false
        WHERE case_id = (c.new_value ->> 'case_id')::uuid AND user_id = c.subject_user_id;
        UPDATE users SET authz_version = authz_version + 1 WHERE id = c.subject_user_id;
    ELSIF c.kind = 'THRESHOLDS' THEN
        SELECT coalesce(max(thresholds_version), 0) + 1 INTO next_version FROM threshold_versions;
        INSERT INTO threshold_versions (thresholds_version, high_min, medium_min, approved_change_id)
        VALUES (
            next_version, (c.new_value ->> 'high_min')::numeric, (c.new_value ->> 'medium_min')::numeric,
            c.id
        );
    ELSE
        RAISE EXCEPTION 'unknown change kind %', c.kind;
    END IF;
    UPDATE pending_changes SET applied = true WHERE id = c.id;
END;
$$;
