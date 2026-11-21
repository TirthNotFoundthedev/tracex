-- Four-eyes in the database. tracex_api may insert only a PENDING proposal, and may move a
-- PENDING row to DENIED, or to APPROVED only when the decider is an active SENIOR who is not
-- the proposer or the subject and the approved hash equals the proposed hash. A decided row
-- never changes its decision. apply_change trusts only rows that passed these rules.

CREATE FUNCTION pending_changes_guard_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.state <> 'PENDING' OR NEW.decider_id IS NOT NULL OR NEW.decided_at IS NOT NULL
       OR NEW.approved_hash IS NOT NULL OR NEW.applied THEN
        RAISE EXCEPTION 'a pending change must be inserted as an undecided proposal'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER pending_changes_insert_undecided
    BEFORE INSERT ON pending_changes
    FOR EACH ROW EXECUTE FUNCTION pending_changes_guard_insert();

CREATE FUNCTION pending_changes_guard_update() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    approver users%ROWTYPE;
BEGIN
    IF OLD.state <> 'PENDING' THEN
        IF NEW.state IS DISTINCT FROM OLD.state OR NEW.decider_id IS DISTINCT FROM OLD.decider_id
           OR NEW.decided_at IS DISTINCT FROM OLD.decided_at
           OR NEW.approved_hash IS DISTINCT FROM OLD.approved_hash THEN
            RAISE EXCEPTION 'a decided change cannot be decided again'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.state = 'PENDING' THEN
        IF NEW.decider_id IS NOT NULL OR NEW.decided_at IS NOT NULL
           OR NEW.approved_hash IS NOT NULL THEN
            RAISE EXCEPTION 'a pending change has no decision fields'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.decider_id IS NULL OR NEW.decided_at IS NULL THEN
        RAISE EXCEPTION 'a decision needs a decider and a time' USING ERRCODE = 'check_violation';
    END IF;
    SELECT * INTO approver FROM users WHERE id = NEW.decider_id;
    IF NOT FOUND OR NOT approver.active OR approver.role <> 'SENIOR' THEN
        RAISE EXCEPTION 'only an active SENIOR may decide a change'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.state = 'APPROVED' AND NEW.approved_hash IS DISTINCT FROM OLD.change_hash THEN
        RAISE EXCEPTION 'the approved hash must equal the proposed hash'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.state = 'DENIED' AND NEW.approved_hash IS NOT NULL THEN
        RAISE EXCEPTION 'a denied change has no approved hash' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER pending_changes_update_rules
    BEFORE UPDATE ON pending_changes
    FOR EACH ROW EXECUTE FUNCTION pending_changes_guard_update();
