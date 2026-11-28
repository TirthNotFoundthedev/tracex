-- One waiting change per target (TIR-91). The API checks this first for a clear answer, but the
-- index is what enforces it, so two proposals sent at the same moment cannot both be stored.
-- Target: the kind, the subject user, and the case of an assignment change or the username of
-- an account to create. THRESHOLDS are left out: their old value protects them at approval.
CREATE UNIQUE INDEX pending_changes_one_waiting ON pending_changes (
    kind,
    coalesce(subject_user_id, '00000000-0000-0000-0000-000000000000'::uuid),
    coalesce(new_value ->> 'case_id', new_value ->> 'username', '')
) WHERE state = 'PENDING' AND kind <> 'THRESHOLDS';
