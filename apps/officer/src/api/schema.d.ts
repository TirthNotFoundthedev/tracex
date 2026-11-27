export interface paths {
  "/health": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Liveness */
    get: operations["getHealth"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/ready": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Readiness (database, graph store, audit chain startup check) */
    get: operations["getReady"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Sign in with a seeded username and password
     * @description Access token 15 minutes, refresh token 8 hours absolute. Claims: `sub`, `sid`, `iat`, `exp`, `jti`, `ver`;
     *     role and jurisdiction are never claims. Five failed logins per (username string, IP) in 15 minutes give 429 for
     *     15 minutes, whether or not the username exists. There is no route to set or reset a password.
     */
    post: operations["login"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/refresh": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Rotate a refresh token
     * @description Single use. Presenting a rotated refresh token again revokes the whole session (`sid`) and is audited.
     */
    post: operations["refreshToken"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * End the current session
     * @description Marks the session dead in the database; the access token stops working at once.
     */
    post: operations["logout"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** The signed-in user, read from the database */
    get: operations["getMe"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/cases": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Cases the caller may see (own cases and own jurisdiction)
     * @description `district_id` and `case_number` filters only narrow; they never widen scope (A42). `linked_item_count` counts
     *     ALLOW links only.
     */
    get: operations["listCases"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/cases/{case_id}/entities": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * A case and its entities (people, phones, accounts, vehicles)
     * @description Returns the case header and the entities of that case. `link_count` counts ALLOW links only;
     *     `has_hidden_connection` is true when at least one stub exists for the entity; `needs_review` is true when an
     *     ALLOW SUGGESTED link waits on the entity. Low-band pairs are never stored and appear nowhere.
     */
    get: operations["listCaseEntities"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/entities/{entity_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * One entity with its visible links and stubs
     * @description `links` are ALLOW links (at most 50, newest first; page the rest with `GET /links?entity_id=`). `stubs` are one per hidden link, same shape whatever the link state, ordered by `stub_id`, after the visible items. A stub never carries far-side fields. Under a grant (`via_grant` true) the far entity shows only the granted link: `link_count` 1, `has_hidden_connection` false, `needs_review` false, `stubs` empty, provenance only for the cited lines.
     */
    get: operations["getEntity"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/search/entities": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Find entities by value
     * @description Matches ALLOW entities only. A value that exists only in a hidden entity returns the same empty result as no
     *     match, with no stubs. Search terms are never stored in the audit log.
     */
    get: operations["searchEntities"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/documents/{document_id}/lines": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Source lines of a document
     * @description By role and relation: JUNIOR own case only; INVESTIGATOR and above own case and own jurisdiction. Under a
     *     grant, only the exact cited line ranges fixed at approval, and never for a JUNIOR (role cap). Answers 403 when
     *     the case is visible to the caller but the role cell is DENY (a JUNIOR in own jurisdiction, A4) and for a range
     *     outside the grant's fixed ranges on a document the grant covers (A23). A document of a hidden case, an unknown
     *     id and any call by ADMIN answer 404.
     */
    get: operations["getSourceLines"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Links the caller may see, plus stubs for those they may not
     * @description ALLOW links first, then stubs ordered by `stub_id`. Stubs appear only for links with an end on a visible entity of the caller. **The stub set never depends on `state` or `entity_type`**: those filters narrow the visible links only, so stub counts cannot reveal the state of a hidden link. `total` counts ALLOW links only. Rejected and undone links are listed only when `state` asks for them. For decision work use `GET /review-queue`.
     */
    get: operations["listLinks"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links/{link_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * One link in full
     * @description Only when the caller has ALLOW on both end cases (or an active grant on this link). A REDACTED link answers the
     *     same 404 as a random id. The response says which decisions this caller may take (`allowed_actions`) and, when
     *     none, why in a code (`decision_block`), so the app can show the right line without re-deriving rules.
     */
    get: operations["getLink"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links/{link_id}/explanation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Why the link exists (explanation payload)
     * @description Returns the payload of `explanation.schema.json`: codes, numbers and ids; wording is rendered by the client from
     *     `template_key` and `params`. A REDACTED link answers 404; use the stub. Under a grant the cited-line set is
     *     fixed at approval.
     */
    get: operations["getLinkExplanation"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links/{link_id}/confirm": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Confirm a SUGGESTED or AUTO link
     * @description SUGGESTED -> CONFIRMED and AUTO -> CONFIRMED. Both end cases must be ALLOW for the caller by their own scope
     *     (R3); a link across districts or states is decided only by a SENIOR whose coverage includes both ends; a grant
     *     never qualifies (403, `decision_block` GRANT_READ_ONLY). Any other source state answers 409
     *     `INVALID_TRANSITION`.
     *     While a matching run is RUNNING this answers 409 `RUN_IN_PROGRESS` (state unchanged).
     */
    post: operations["confirmLink"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links/{link_id}/reject": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reject a SUGGESTED link
     * @description SUGGESTED -> REJECTED with a required reason. An AUTO link cannot be rejected (409 `INVALID_TRANSITION`);
     *     it can only be undone. The rejected pair joins the block list (the REJECTED edge itself); it is never proposed
     *     again. The reason is stored on the link history, never in the audit log.
     *     While a matching run is RUNNING this answers 409 `RUN_IN_PROGRESS` (state unchanged).
     */
    post: operations["rejectLink"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links/{link_id}/undo": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Undo an AUTO or CONFIRMED link
     * @description AUTO -> UNDONE or CONFIRMED -> UNDONE with a required reason. Entities, provenance and the edge with its
     *     history remain; the pair is not auto-linked again; clusters split on the next read.
     *     While a matching run is RUNNING this answers 409 `RUN_IN_PROGRESS` (state unchanged).
     */
    post: operations["undoLink"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/links/{link_id}/reopen": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reopen a REJECTED or UNDONE link as SUGGESTED
     * @description REJECTED -> SUGGESTED and UNDONE -> SUGGESTED with a required reason (D34: surfaced in the admin panel review queue under the Rejected filter). A reopened pair is ended only by a human (CONFIRMED, or REJECTED again); it never becomes AUTO and a rerun never withdraws it.
     *     While a matching run is RUNNING this answers 409 `RUN_IN_PROGRESS` (state unchanged).
     */
    post: operations["reopenLink"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/review-queue": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Links awaiting or open to a human decision
     * @description ALLOW items only; a stub never appears here and queue sizes count ALLOW items only. `state` defaults to SUGGESTED (Waiting). `REJECTED` and `UNDONE` list decided links so a SUPERVISOR or SENIOR can reopen them (D34). Filters (`district_id`, `entity_type`, `waiting_days_min`) only narrow. Each item carries the main reason (highest-contribution support item) as a template key plus params. REJECTED and UNDONE items carry `last_decision` (time, reason, and the deciding person when the caller may know them, access spec 4.2). `total` counts the ALLOW items that match the filters. ADMIN answers 404.
     */
    get: operations["listReviewQueue"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/entities/{entity_id}/graph": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Per-viewer graph neighbours of an entity
     * @description Nodes and edges within `depth` hops over ALLOW links, capped at `limit` nodes (default 150, nearest first;
     *     `truncated` says so). A hidden link is an unlabelled leaf stub with no far-side edges. Degree counts ALLOW
     *     edges only.
     *     Traversal runs over ALLOW edges only and is pruned at the first hidden edge; it is never a filter applied afterwards, so an entity reachable only through a hidden link does not appear. `truncated` is computed after pruning.
     */
    get: operations["getEntityGraph"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/entities/{entity_id}/cluster": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * The identity cluster of an entity, as this viewer may see it
     * @description A cluster is a connected component of active (AUTO, CONFIRMED) links of one entity type, derived on read. The
     *     response is computed per viewer: any link with an end case the viewer lacks ALLOW on is a hideable segment and
     *     becomes a stub; members beyond it are not listed. No implied links are drawn. `cluster_id` is a fresh random
     *     handle for this response only: it is not derived from member ids, is not stable between calls and cannot be
     *     fetched.
     *     Membership is computed by traversal over ALLOW active edges pruned at the first hidden edge, never filtered afterwards.
     */
    get: operations["getEntityCluster"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/entities/{entity_id}/paths": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Paths of active links leading out of an entity, as this viewer may see them
     * @description Each path is a list of segments over active links, up to `max_hops`. A segment is VISIBLE (link and far entity)
     *     or STUB; a stub ends its path: nothing beyond a hidden segment is listed. Path ids are random per response.
     *     Paths are built over ALLOW edges and end at the first hidden segment.
     */
    get: operations["getEntityPaths"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/stubs/{stub_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * One stub (a hidden connection) and the caller's request status for it
     * @description The stub only; never a link-id route. A stub id belongs to one caller; another caller's id, a link id, a case id
     *     and an entity id all answer the same 404.
     */
    get: operations["getStub"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/access-requests": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Requests the caller made, or may decide
     * @description `scope=mine`: the caller's own requests with their status (the officer app shows decisions from here).
     *     `scope=to_decide`: requests whose far case lies in the caller's authority (SUPERVISOR of that district, or
     *     SENIOR covering it); each shows the requester, the reason and a stub of the near side. Requests of others
     *     outside that authority do not exist for the caller.
     */
    get: operations["listAccessRequests"];
    put?: never;
    /**
     * Ask for access through one stub
     * @description One request per stub: one link, one far case; no fan-out. Reason 10 to 500 characters, no personal data. At most
     *     10 PENDING per user. After a denial the same stub can be requested again only after 24 hours (409
     *     `REQUEST_COOLDOWN`). A request with a link, case or entity id instead of a stub id, or another user's stub,
     *     answers 404. A request on an own case is not possible: no stub exists for it.
     */
    post: operations["createAccessRequest"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/access-requests/{request_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * One access request
     * @description Visible to the requester and to an approver with authority over the far case; 404 for everyone else.
     */
    get: operations["getAccessRequest"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/access-requests/{request_id}/withdraw": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Withdraw the caller's own PENDING request */
    post: operations["withdrawAccessRequest"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/access-requests/{request_id}/approve": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Approve a request and create the grant
     * @description The approver chooses 7, 30 or 90 days (default 30). The grant is read-only, covers the far entity of that one
     *     link, its explanation and the exact source-line ranges its evidence cites at this moment (fixed now), capped by
     *     the requester's role in their own jurisdiction. Never the requester (403, they can see it), never ADMIN, and a
     *     caller without authority over the far case gets 404.
     */
    post: operations["approveAccessRequest"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/access-requests/{request_id}/deny": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Deny a request
     * @description The optional note is shown to the requester; it is stored on the request, never in the audit log.
     */
    post: operations["denyAccessRequest"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/grants": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Grants the caller holds, or has authority over
     * @description `scope=held`: grants the caller received. `scope=authority`: grants on cases in the caller's authority (the
     *     approving SUPERVISOR or SENIOR). A grant outside those two views does not exist for the caller.
     */
    get: operations["listGrants"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/grants/{grant_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * One grant
     * @description The holder and an authority over the far case see it; anyone else gets 404.
     */
    get: operations["getGrant"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/grants/{grant_id}/revoke": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Revoke an ACTIVE grant (effective on the holder's next request) */
    post: operations["revokeGrant"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/uploads": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Upload batches and their status */
    get: operations["listUploads"];
    put?: never;
    /**
     * Upload case material
     * @description One batch per file. `case_number` is unique per district, so the pair (`district_id`, `case_number`) names the case. The response is identical for a new and an existing case: batch ids and file facts only, no case id, title or created flag, no different status or error. Accepted residual: an ADMIN can learn that a case number exists in a district they name (also through a proposal's 422). Parsing runs after the response (status moves WAITING, READING, DONE, FAILED).
     */
    post: operations["uploadFiles"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/uploads/{batch_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** One upload batch */
    get: operations["getUpload"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/matching/runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Matching runs, newest first */
    get: operations["listMatchingRuns"];
    put?: never;
    /**
     * Start a matching run over all cases
     * @description Runs are batch and jurisdiction-blind. The scope is by upload batch (`batch_ids`, or every batch not yet run); new input is matched against all loaded cases. The run reads `thresholds_version` once at start. **Guard:** a run starts only when the decision outbox has no unacknowledged row, and while a run is RUNNING the four decision operations answer 409 `RUN_IN_PROGRESS`; both directions use the same code. The engine returns transition records; the API rejects any record whose `from` state does not equal the Postgres state, and otherwise writes the link rows and audit rows (LINK_AUTO_CREATED, LINK_SUGGESTED, LINK_DEMOTED, LINK_PROMOTED, LINK_WITHDRAWN, SYSTEM actor). A WITHDRAWN link keeps its row in state WITHDRAWN (never deleted, never readable, not block-listed). The response and the run record expose totals of AUTO and SUGGESTED created only: no LOW count, no per-case or per-pair counts.
     */
    post: operations["startMatchingRun"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/matching/runs/{run_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** One matching run */
    get: operations["getMatchingRun"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/jurisdictions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** States and their districts */
    get: operations["listJurisdictions"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/roles": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** The five roles with i18n keys for their names and descriptions */
    get: operations["listRoles"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/users": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Users the caller may see
     * @description ADMIN sees all users. A SENIOR sees users whose jurisdiction lies in their coverage. Case assignments are shown
     *     as a count only; case ids never appear. There is no route to set or reset a password.
     */
    get: operations["listUsers"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/users/{user_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** One user */
    get: operations["getUser"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/thresholds": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Current match thresholds (0 to 100 scale)
     * @description Bands: High at or above `high_min`, Medium from `medium_min`, Low below it (never stored). Changes go through `POST /pending-changes` with kind THRESHOLDS and need a SENIOR with all-state coverage.
     */
    get: operations["getThresholds"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/pending-changes": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Pending changes the caller proposed or may decide
     * @description ADMIN sees changes they proposed. A SENIOR sees changes whose every touched jurisdiction (the subject's old and new district, the district of an assignment's case) lies in their coverage; threshold changes, ADMIN subjects and role changes to or from SENIOR or ADMIN only to an all-state SENIOR. Others do not exist for the caller.
     */
    get: operations["listPendingChanges"];
    put?: never;
    /**
     * Propose a change to users, roles, jurisdictions, assignments or thresholds
     * @description Nothing applies until a SENIOR approves. The server records `old_value` itself and computes `change_hash`
     *     (SHA-256 of the canonical content). Thresholds: 70 <= high_min <= 100 and 30 <= medium_min <= high_min - 10.
     *     Case assignments name the case by `case_number`; an unknown number answers the same 422 as an invalid one.
     *     USER_CREATE makes an account with no usable password; a login for it fails exactly like a wrong password. No route sets or resets a password.
     */
    post: operations["proposeChange"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/pending-changes/{change_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** One pending change */
    get: operations["getPendingChange"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/pending-changes/{change_id}/approve": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Approve a pending change and apply it
     * @description The approver presents the `change_hash` they saw. A changed proposal is a new record needing new approval
     *     (409 `CHANGE_HASH_STALE`). If the current value no longer equals `old_value`, 409 `OLD_VALUE_CHANGED`.
     *     Disabling or moving the last SENIOR able to approve a jurisdiction is refused (409 `LAST_APPROVER`). Not the
     *     proposer and not the subject (403). Applying a change that alters a user's role, jurisdiction, assignment or
     *     active flag bumps that user's `authz_version`: old tokens 401, refresh tokens revoked, grants closed.
     */
    post: operations["approveChange"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/pending-changes/{change_id}/deny": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Deny a pending change */
    post: operations["denyChange"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/audit": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read the audit log under the row-level rule
     * @description JUNIOR and INVESTIGATOR: 403. SUPERVISOR, SENIOR and ADMIN read under one row-level rule; a row exists for the
     *     reader only if:
     *     (a) the reader is the actor; or
     *     (b) the actor is in the reader's chain of command (SUPERVISOR or SENIOR: actor district inside their scope or
     *     coverage), including the actor's denied probes; or
     *     (c) `refs` is non-empty and the reader has ALLOW on every case in `refs`, judged by **case-level access**
     *     (own case, own jurisdiction or coverage); a grant never counts; or
     *     (d) the row **references no cases** (`refs` empty) and is a system event (AUTH_*, DATA_UPLOADED, MATCHING_RUN_*, CHANGE_*, USER_*, AUDIT_*) and the reader is ADMIN, or a SENIOR for whom every user and district the row names (the actor's district, the target, the subject, old and new values, `claimed_username` and `claimed_sub`; an actor without a jurisdiction, such as ADMIN or SYSTEM, does not count) lies inside their coverage. An all-state SENIOR sees every such row. Rule (d) never admits a row that references a case.
     *
     *     Rows that fail the rule do not exist for the reader: no placeholder, no gap, no count. For a row shown under (a)
     *     or (b) that references a case the reader cannot see, hidden `refs` entries, every field owned by those cases
     *     and every joint field are dropped (keys absent, not null). Every `detail` key has an owning case
     *     (`audit_detail_key_owner`): a key whose owning case is not in `refs` cannot be written.
     *
     *     Filters, sorting and paging run only over the rows and fields the reader can see. A filter on a value the reader
     *     cannot see returns exactly what a filter on a non-existent value returns: same empty page, `result_count` 0 and
     *     `next_cursor` null. The cursor is signed and bound to the reader and the filters (see Paging above). Rows carry
     *     an opaque `row_ref` (HMAC of the row and the reader), never a sequence number, hash or nonce. There is no
     *     export.
     */
    get: operations["listAudit"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/audit/verify": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Verify the audit hash chain against the external anchor
     * @description Returns `OK` or `BROKEN` plus `first_bad_seq` and nothing else: no rows, no hashes. Checks contiguity, links,
     *     recomputed hashes and the latest anchor. Also runs nightly server-side.
     */
    post: operations["verifyAuditChain"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/stats/links": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * System-wide link totals by state (ADMIN only)
     * @description One object of totals. No parameters, no breakdown by state-of-case, district, case, entity type or officer, no time series, no list. Officer roles get 404; they keep ALLOW-only counts. `/review-queue` stays 404 for ADMIN.
     */
    get: operations["getLinkTotals"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /** Format: uuid */
    Uuid: string;
    /** @description Case or entity id as issued by the API (a UUID or the seeded id such as `C-101`). Opaque to clients. */
    Id: string;
    /** @description Opaque encrypted token. Do not parse; it carries no sequence number or id. */
    Cursor: string;
    /** @enum {string} */
    Role: "JUNIOR" | "INVESTIGATOR" | "SUPERVISOR" | "SENIOR" | "ADMIN";
    /** @enum {string} */
    EntityType: "PERSON" | "ORG" | "PHONE" | "ACCOUNT" | "VEHICLE";
    /** @enum {string} */
    LinkState: "AUTO" | "SUGGESTED" | "CONFIRMED" | "REJECTED" | "UNDONE";
    /** @enum {string} */
    Band: "HIGH" | "MEDIUM" | "LOW";
    /** @enum {string} */
    ErrorCode:
      | "UNAUTHENTICATED"
      | "FORBIDDEN"
      | "NOT_FOUND"
      | "INVALID_TRANSITION"
      | "STATE_MISMATCH"
      | "REQUEST_COOLDOWN"
      | "REQUEST_LIMIT"
      | "NOT_PENDING"
      | "CHANGE_HASH_STALE"
      | "OLD_VALUE_CHANGED"
      | "LAST_APPROVER"
      | "RUN_IN_PROGRESS"
      | "VALIDATION_FAILED"
      | "TOO_MANY_REQUESTS"
      | "NOT_READY"
      | "INTERNAL";
    /** @description Body of the safety-pause 503. Both values are fixed. */
    SafetyPauseError: {
      /** @enum {string} */
      code: "NOT_READY";
      /** @enum {string} */
      message_key: "error.not_ready";
    };
    Error: {
      code: components["schemas"]["ErrorCode"];
      /** @description i18n key; the client owns the wording. Fixed per code. */
      message_key: string;
      /** @description 422 only. Field names and codes only, never echoing submitted values. */
      field_errors?: {
        field: string;
        code: string;
      }[];
    };
    HealthStatus: {
      /** @enum {string} */
      status: "ok";
    };
    LoginRequest: {
      username: string;
      /** Format: password */
      password: string;
    };
    RefreshRequest: {
      refresh_token: string;
    };
    TokenPair: {
      access_token: string;
      refresh_token: string;
      /** @enum {string} */
      token_type: "Bearer";
      /**
       * @description Seconds (15 minutes).
       * @constant
       */
      expires_in: 900;
      /** @description Seconds left of the 8 hour absolute lifetime. */
      refresh_expires_in: number;
      user: components["schemas"]["User"];
    };
    /** @description SENIOR coverage set. Seeded; one SENIOR covers all states. */
    Coverage: {
      /** @description True for the central desk. */
      all_states?: boolean;
      state_ids: components["schemas"]["Uuid"][];
      district_ids: components["schemas"]["Uuid"][];
    };
    User: {
      user_id: components["schemas"]["Uuid"];
      username: string;
      display_name: string;
      role: components["schemas"]["Role"];
      /** @description One district for JUNIOR to SUPERVISOR; null for SENIOR and ADMIN. */
      district_id?: components["schemas"]["Uuid"] | null;
      /** @description SENIOR only. */
      coverage?: components["schemas"]["Coverage"] | null;
      active: boolean;
      /** @description Number of assigned cases; ids are never shown here. */
      assignment_count?: number;
    };
    UserPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["User"][];
    };
    RoleInfo: {
      role: components["schemas"]["Role"];
      name_key: string;
      description_key: string;
      /** @enum {string} */
      scope: "DISTRICT" | "COVERAGE" | "NONE";
    };
    RoleList: {
      items: components["schemas"]["RoleInfo"][];
    };
    District: {
      district_id: components["schemas"]["Uuid"];
      name: string;
    };
    State: {
      state_id: components["schemas"]["Uuid"];
      name: string;
      districts: components["schemas"]["District"][];
    };
    JurisdictionList: {
      items: components["schemas"]["State"][];
    };
    PageBase: {
      /** @description Null on the last page and on every empty page. */
      next_cursor: components["schemas"]["Cursor"] | null;
      /** @description Counts only the items the caller may see (ALLOW), with the page's filters applied; never stubs, grant-only links or hidden items. */
      total: number;
    };
    CaseRefBase: {
      case_id: components["schemas"]["Id"];
      case_number: string;
      title?: string;
      district_id: components["schemas"]["Uuid"];
    };
    CaseRef: components["schemas"]["CaseRefBase"];
    CaseSummary: components["schemas"]["CaseRefBase"] & {
      /** Format: date */
      opened_on: string;
      /** @description Entities of this case that appear in other cases through ALLOW links. */
      linked_item_count: number;
      /** @description True when the caller is assigned to the case. */
      is_assigned?: boolean;
    };
    CasePage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["CaseSummary"][];
    };
    EntitySummaryBase: {
      entity_id: components["schemas"]["Id"];
      case_id: components["schemas"]["Id"];
      type: components["schemas"]["EntityType"];
      /** @description Name, number or registration as stored, or its masked form when `masked` is true. */
      display_value: string;
      /** @description True when any value in this object (`display_value`, a fact) was masked; the full value then appears nowhere in the response. */
      masked: boolean;
      /** @description ALLOW links only. */
      link_count: number;
      /** @description True when at least one stub exists for this entity. */
      has_hidden_connection: boolean;
      /** @description An ALLOW SUGGESTED link waits on this entity. */
      needs_review: boolean;
      /** @description True when the caller reaches this entity only through a grant. */
      via_grant: boolean;
    } & unknown;
    EntitySummary: components["schemas"]["EntitySummaryBase"];
    EntityPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["EntitySummary"][];
    };
    CaseEntitiesPage: components["schemas"]["PageBase"] & {
      case: components["schemas"]["CaseSummary"];
      /** @description Entity count per type for the group headings. */
      counts_by_type?: {
        [key: string]: number;
      };
      items: components["schemas"]["EntitySummary"][];
    };
    /** @description Where an entity came from. Pointers only; line text comes from the source-lines route under its own rule. */
    Provenance: {
      case_id: components["schemas"]["Id"];
      document_id: string;
      line: number;
      page?: number | null;
      document_type?: string | null;
    };
    EntityFact: {
      /** @description i18n key suffix for the label (for example `age`, `address`). */
      key: string;
      value: string;
    };
    EntityDetail: components["schemas"]["EntitySummaryBase"] & {
      case: components["schemas"]["CaseRef"];
      facts: components["schemas"]["EntityFact"][];
      provenance: components["schemas"]["Provenance"][];
      links: components["schemas"]["LinkSummary"][];
      stubs: components["schemas"]["Stub"][];
      /** @description True when the caller sees this entity only through a grant. */
      via_grant: boolean;
    };
    SourceLine: {
      line: number;
      page?: number | null;
      text: string;
    };
    SourceLines: {
      document_id: string;
      case_id: components["schemas"]["Id"];
      document_type: string;
      lines: components["schemas"]["SourceLine"][];
      via_grant: boolean;
    };
    LinkEnd: {
      entity: components["schemas"]["EntitySummary"];
      case: components["schemas"]["CaseRef"];
    };
    /** @description The highest-contribution support item of the explanation; the client renders it like any explanation line. */
    MainReason: {
      template_key: string;
      params: Record<string, never>;
      /** @description True when a param value was masked. */
      masked?: boolean;
    };
    LinkSummaryBase: {
      link_id: components["schemas"]["Uuid"];
      entity_type: components["schemas"]["EntityType"];
      state: components["schemas"]["LinkState"];
      band: components["schemas"]["Band"];
      score: number;
      ends: components["schemas"]["LinkEnd"][];
      main_reason: components["schemas"]["MainReason"];
      /** Format: date-time */
      updated_at: string;
    };
    LinkSummary: components["schemas"]["LinkSummaryBase"];
    /** @enum {string} */
    AllowedAction: "CONFIRM" | "REJECT" | "UNDO" | "REOPEN";
    /**
     * @description Why no decision is open to this caller, as a code the app maps to its sentence (design O6). ROLE_VIEW_ONLY: role below the needed one. CROSS_AREA_SENIOR_ONLY: the link joins two areas and the caller is not a SENIOR. COVERAGE_INCOMPLETE: a SENIOR who does not cover both ends. GRANT_READ_ONLY: access is by grant, which never qualifies. STATE_FINAL: no transition is legal from the current state for this role.
     * @enum {string}
     */
    DecisionBlock:
      | "ROLE_VIEW_ONLY"
      | "CROSS_AREA_SENIOR_ONLY"
      | "COVERAGE_INCOMPLETE"
      | "GRANT_READ_ONLY"
      | "STATE_FINAL";
    HistoryEntry: {
      from: components["schemas"]["LinkState"] | null;
      to: components["schemas"]["LinkState"] | null;
      /** Format: date-time */
      at: string;
      /** @enum {string} */
      actor_kind: "ENGINE" | "USER";
      actor_user_id?: components["schemas"]["Uuid"] | null;
      /** @description The deciding person, only when the caller may already know them (access spec 4.2 - the caller is the actor, a SUPERVISOR in the chain of command, or a SENIOR who could read them through `GET /users/{user_id}`). Null otherwise, with no role, district or partial name; always null for an engine entry. */
      actor: components["schemas"]["UserRef"] | null;
      reason_code: string | null;
      /** @description Free text from the deciding officer. Shown only to callers with ALLOW on both ends by their own scope; never under a grant. */
      reason_text?: string | null;
    };
    LinkDetail: components["schemas"]["LinkSummaryBase"] &
      ({
        thresholds_version: number;
        ruleset_version: string;
        /** Format: date-time */
        created_at: string;
        history: (
          components["schemas"]["HistoryEntry"] | components["schemas"]["HistoryEntryGranted"]
        )[];
        allowed_actions: components["schemas"]["AllowedAction"][];
        decision_block?: components["schemas"]["DecisionBlock"] | null;
        via_grant: boolean;
      } & unknown);
    LinkPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["LinkSummary"][];
      /** @description After the visible items, ordered by `stub_id`. */
      stubs: components["schemas"]["Stub"][];
    };
    ReviewQueueItem: components["schemas"]["LinkSummaryBase"] & {
      /** Format: date-time */
      waiting_since: string;
      allowed_actions: components["schemas"]["AllowedAction"][];
      /** @description The last human decision on a REJECTED or UNDONE item. Null for a SUGGESTED item. */
      last_decision: components["schemas"]["LastDecision"] | null;
    };
    /** @description The last human decision on a queue item. `reason_text` follows the link history rule (access spec 4.2); queue items are ALLOW by own scope only, so every caller who gets the item gets the reason. */
    LastDecision: {
      to: components["schemas"]["LinkState"];
      /** Format: date-time */
      at: string;
      /** @description Same rule as `HistoryEntry.actor`. */
      actor: components["schemas"]["UserRef"] | null;
      reason_text: string | null;
    };
    ReviewQueuePage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["ReviewQueueItem"][];
    };
    ConfirmLinkRequest: {
      expected_state?: components["schemas"]["LinkState"];
    };
    LinkReasonRequest: {
      /** @description Stored on the link history only; never in the audit log. */
      reason: string;
      expected_state?: components["schemas"]["LinkState"];
    };
    Explanation: components["schemas"]["explanation.schema"];
    /** @enum {string} */
    AccessRequestStatus: "PENDING" | "APPROVED" | "DENIED" | "WITHDRAWN" | "EXPIRED";
    /** @enum {string} */
    StubRequestState: "NONE" | "PENDING" | "DENIED" | "EXPIRED";
    /**
     * @description One hidden link, same shape whatever its state. It never carries a far case id, number, title, district or
     *     officer; a far entity id, type, name or value; or a link id, state, score, band, tier, signals, evidence count,
     *     creation time or run id.
     */
    Stub: {
      /** @constant */
      redacted: true;
      stub_id: components["schemas"]["Uuid"];
      near_entity_id: components["schemas"]["Id"];
      /** @constant */
      connection_exists: true;
      access_request: {
        status: components["schemas"]["StubRequestState"];
        /** Format: date-time */
        requested_at?: string | null;
      };
      /** @constant */
      message_key: "access.stub.connection_exists";
    };
    CreateAccessRequest: {
      stub_id: components["schemas"]["Uuid"];
      /** @description No personal data. Stored on the request only. */
      reason: string;
    };
    ApproveAccessRequest: {
      /**
       * @default 30
       * @enum {integer}
       */
      duration_days: 7 | 30 | 90;
    };
    DenyAccessRequest: {
      /** @description Shown to the requester. Must carry no case detail (names, numbers, places); the UI says so. Stored on the request, never in the audit log. */
      note?: string;
    };
    /** @enum {string} */
    GrantStatus: "ACTIVE" | "EXPIRED" | "REVOKED";
    /** @enum {string} */
    GrantCloseCause: "MANUAL" | "ROLE_CHANGE" | "LINK_CLOSED" | "EVIDENCE_CHANGED" | "TIME";
    Grant: components["schemas"]["GrantHeld"] | components["schemas"]["GrantAuthority"];
    GrantPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["Grant"][];
    };
    UserRef: {
      user_id: components["schemas"]["Uuid"];
      display_name: string;
      role: components["schemas"]["Role"];
    };
    AccessRequest:
      components["schemas"]["AccessRequestMine"] | components["schemas"]["AccessRequestToDecide"];
    AccessRequestPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["AccessRequest"][];
    };
    GraphNode: {
      entity: components["schemas"]["EntitySummary"];
      /** @description ALLOW edges only. */
      degree: number;
      distance: number;
    };
    GraphEdge: {
      link_id: components["schemas"]["Uuid"];
      state: components["schemas"]["LinkState"];
      band: components["schemas"]["Band"];
      from_entity_id: components["schemas"]["Id"];
      to_entity_id: components["schemas"]["Id"];
    };
    GraphResponse: {
      center_entity_id: components["schemas"]["Id"];
      nodes: components["schemas"]["GraphNode"][];
      edges: components["schemas"]["GraphEdge"][];
      /** @description Unlabelled leaves with no far-side edges. */
      stubs: components["schemas"]["Stub"][];
      truncated: boolean;
    };
    ClusterResponse: {
      cluster_id: components["schemas"]["Uuid"];
      entity_type: components["schemas"]["EntityType"];
      members: components["schemas"]["EntitySummary"][];
      links: components["schemas"]["LinkSummary"][];
      stubs: components["schemas"]["Stub"][];
      /** @description Stretch indicator (PLAN C1); a visible member with the most ALLOW links, or null. */
      most_connected_entity_id?: components["schemas"]["Id"] | null;
    };
    PathSegmentVisible: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      kind: "VISIBLE";
      link: components["schemas"]["LinkSummary"];
      entity: components["schemas"]["EntitySummary"];
    };
    PathSegmentStub: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      kind: "STUB";
      stub: components["schemas"]["Stub"];
    };
    PathSegment:
      components["schemas"]["PathSegmentVisible"] | components["schemas"]["PathSegmentStub"];
    Path: {
      path_id: components["schemas"]["Uuid"];
      segments: components["schemas"]["PathSegment"][];
    };
    PathsResponse: {
      origin_entity_id: components["schemas"]["Id"];
      paths: components["schemas"]["Path"][];
    };
    UploadRequest: {
      /** @description An existing or new case number; the ADMIN cannot list cases. */
      case_number: string;
      district_id: components["schemas"]["Uuid"];
      /** @description PDF, Word, Excel, text or images. */
      files: string[];
    };
    /** @enum {string} */
    BatchStatus: "WAITING" | "READING" | "DONE" | "FAILED";
    UploadBatch: {
      batch_id: components["schemas"]["Uuid"];
      file_name: string;
      file_sha256: string;
      byte_count: number;
      document_count?: number;
      status: components["schemas"]["BatchStatus"];
      /** @description Reason code for FAILED; the app renders it in words. */
      error_code?: string | null;
      /** Format: date-time */
      created_at: string;
    };
    UploadResponse: {
      batches: components["schemas"]["UploadBatch"][];
    };
    UploadBatchPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["UploadBatch"][];
    };
    /** @enum {string} */
    RunStatus: "RUNNING" | "SUCCEEDED" | "FAILED";
    /** @description The engine's run record as the API persists it, reduced for ADMIN. `input_case_ids` and per-state, per-band and per-pair counts stay in the database; the response has totals of AUTO and SUGGESTED created only. */
    MatchRun: {
      run_id: components["schemas"]["Uuid"];
      status: components["schemas"]["RunStatus"];
      /** Format: date-time */
      started_at: string;
      /** Format: date-time */
      finished_at?: string | null;
      triggered_by: components["schemas"]["Uuid"];
      ruleset_version: string;
      thresholds_version: number;
      oversized_block_count: number;
      error_code?: string | null;
      input_batch_count: number;
      auto_created: number;
      suggested_created: number;
    };
    MatchRunPage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["MatchRun"][];
    };
    Thresholds: {
      high_min: number;
      medium_min: number;
      thresholds_version: number;
      /** Format: date-time */
      effective_at: string;
    };
    /** @enum {string} */
    ChangeKind:
      | "USER_CREATE"
      | "USER_ENABLE"
      | "USER_DISABLE"
      | "USER_ROLE"
      | "USER_JURISDICTION"
      | "ASSIGNMENT_ADD"
      | "ASSIGNMENT_REMOVE"
      | "THRESHOLDS";
    /** @enum {string} */
    ChangeState: "PENDING" | "APPROVED" | "DENIED";
    ProposeUserCreate: {
      /** @constant */
      kind: "USER_CREATE";
      /** @description `district_id` for district roles, `coverage` for SENIOR; never both (422). */
      new_value: {
        username: string;
        display_name: string;
        role: components["schemas"]["Role"];
        district_id?: components["schemas"]["Uuid"];
        coverage?: components["schemas"]["Coverage"];
      };
    };
    ProposeUserActive: {
      /** @enum {string} */
      kind: "USER_ENABLE" | "USER_DISABLE";
      subject_user_id: components["schemas"]["Uuid"];
    };
    ProposeUserRole: {
      /** @constant */
      kind: "USER_ROLE";
      subject_user_id: components["schemas"]["Uuid"];
      new_value: {
        role: components["schemas"]["Role"];
      };
    };
    ProposeUserJurisdiction: {
      /** @constant */
      kind: "USER_JURISDICTION";
      subject_user_id: components["schemas"]["Uuid"];
      /** @description One of `district_id` (district roles) or `coverage` (SENIOR), never both. A value that carries both is refused with 422. */
      new_value: {
        district_id?: components["schemas"]["Uuid"];
        coverage?: components["schemas"]["Coverage"];
      } & (unknown | unknown);
    };
    ProposeAssignment: {
      /** @enum {string} */
      kind: "ASSIGNMENT_ADD" | "ASSIGNMENT_REMOVE";
      subject_user_id: components["schemas"]["Uuid"];
      new_value: {
        case_number: string;
      };
    };
    ProposeThresholds: {
      /** @constant */
      kind: "THRESHOLDS";
      new_value: {
        high_min: number;
        medium_min: number;
      };
    };
    ProposeChangeRequest:
      | components["schemas"]["ProposeUserCreate"]
      | components["schemas"]["ProposeUserActive"]
      | components["schemas"]["ProposeUserRole"]
      | components["schemas"]["ProposeUserJurisdiction"]
      | components["schemas"]["ProposeAssignment"]
      | components["schemas"]["ProposeThresholds"];
    PendingChange: {
      change_id: components["schemas"]["Uuid"];
      kind: components["schemas"]["ChangeKind"];
      state: components["schemas"]["ChangeState"];
      subject?: components["schemas"]["UserRef"] | null;
      /** @description Recorded by the server at proposal time. */
      old_value: Record<string, never> | null;
      new_value: Record<string, never>;
      proposer: components["schemas"]["UserRef"];
      decider?: components["schemas"]["UserRef"] | null;
      /** @description SHA-256 of the canonical content. */
      change_hash: string;
      /** Format: date-time */
      proposed_at: string;
      /** Format: date-time */
      decided_at?: string | null;
    };
    PendingChangePage: components["schemas"]["PageBase"] & {
      items: components["schemas"]["PendingChange"][];
    };
    ApproveChangeRequest: {
      change_hash: string;
    };
    /** @enum {string} */
    AuditEventType:
      | "AUDIT_CHAIN_STARTED"
      | "AUTH_LOGIN_SUCCESS"
      | "AUTH_LOGIN_FAILED"
      | "AUTH_LOGOUT"
      | "AUTH_REFRESHED"
      | "AUTH_TOKEN_REJECTED"
      | "AUTH_REFRESH_REUSED"
      | "CASE_LISTED"
      | "CASE_ENTITIES_VIEWED"
      | "ENTITY_VIEWED"
      | "LINK_VIEWED"
      | "STUB_VIEWED"
      | "GRAPH_VIEWED"
      | "REVIEW_QUEUE_VIEWED"
      | "EXPLANATION_VIEWED"
      | "SOURCE_LINES_VIEWED"
      | "SEARCH_RUN"
      | "ACCESS_DENIED"
      | "LINKS_LISTED"
      | "LINK_AUTO_CREATED"
      | "LINK_SUGGESTED"
      | "LINK_DEMOTED"
      | "LINK_CONFIRMED"
      | "LINK_REJECTED"
      | "LINK_UNDONE"
      | "LINK_REOPENED"
      | "ACCESS_REQUEST_CREATED"
      | "ACCESS_REQUEST_WITHDRAWN"
      | "ACCESS_REQUEST_EXPIRED"
      | "ACCESS_REQUEST_APPROVED"
      | "ACCESS_REQUEST_REJECTED"
      | "ACCESS_GRANT_REVOKED"
      | "ACCESS_GRANT_EXPIRED"
      | "ACCESS_GRANT_CLOSED"
      | "DATA_UPLOADED"
      | "MATCHING_RUN_STARTED"
      | "MATCHING_RUN_COMPLETED"
      | "CHANGE_PROPOSED"
      | "CHANGE_APPROVED"
      | "CHANGE_DENIED"
      | "ASSIGNMENT_CHANGED"
      | "USER_CREATED"
      | "USER_ENABLED"
      | "USER_DISABLED"
      | "AUDIT_VIEWED"
      | "AUDIT_VERIFY_RUN"
      | "LINK_PROMOTED"
      | "LINK_WITHDRAWN"
      | "ACCESS_REQUEST_VIEWED"
      | "GRANT_VIEWED"
      | "CHANGE_VIEWED"
      | "ENGINE_DIVERGENCE_REVERTED";
    AuditActor: {
      /** @enum {string} */
      kind: "USER" | "SYSTEM" | "ANONYMOUS";
      user_id?: components["schemas"]["Uuid"];
      role?: components["schemas"]["Role"];
      district_id?: components["schemas"]["Uuid"];
    };
    AuditCaseRef: {
      case_id: components["schemas"]["Id"];
      district_id: components["schemas"]["Uuid"];
    };
    /**
     * @description Never contains a sequence number, event id, hash, nonce, session id, request id or client address. Keys the
     *     reader may not see are absent, not null. `target_id` of an UNRESOLVED target is the string the caller supplied.
     */
    AuditRow: {
      /** @description Opaque; HMAC of the row and the reader. Two readers get different values for the same row. */
      row_ref: string;
      /** Format: date-time */
      occurred_at: string;
      event_type: components["schemas"]["AuditEventType"];
      /** @enum {string} */
      outcome: "SUCCESS" | "DENIED" | "FAILED";
      actor: components["schemas"]["AuditActor"];
      reason_code?: string;
      /** @description Only the cases the reader may see. Empty for system events and for R2_NOT_VISIBLE denials. */
      refs: components["schemas"]["AuditCaseRef"][];
      /** @enum {string} */
      target_type?:
        | "CASE"
        | "ENTITY"
        | "LINK"
        | "STUB"
        | "DOCUMENT"
        | "USER"
        | "ACCESS_REQUEST"
        | "GRANT"
        | "BATCH"
        | "RUN"
        | "SETTING"
        | "CHANGE"
        | "AUDIT"
        | "UNRESOLVED";
      target_id?: string;
      detail?: components["schemas"]["AuditDetail"];
    };
    AuditPage: {
      items: components["schemas"]["AuditRow"][];
      /** @description Encrypted, bound to the reader and the filters, expires after 15 minutes; position is the visible sort key plus `row_ref`, never `seq`. Null on the last page and on every empty page. */
      next_cursor: components["schemas"]["Cursor"] | null;
      /** @description Rows the reader may see that match the filters. */
      result_count: number;
    };
    AuditVerifyResult: {
      /** @enum {string} */
      result: "OK" | "BROKEN";
      /** @description Present only with BROKEN, only to a SENIOR. The single place a sequence number leaves the API (D38, as amended). */
      first_bad_seq?: number | null;
    };
    StartRunRequest: {
      /** @description Optional: upload batches whose cases are new input. Default: every batch not yet run. The server maps the batches to `input_case_ids` for the engine; new input is always matched against all loaded cases, never against a named subset, so the totals say no more than a full run would. A batch id that is unknown answers the same 422 as an invalid one. */
      batch_ids?: components["schemas"]["Uuid"][];
    };
    LinkTotals: {
      waiting: number;
      rejected: number;
      undone: number;
      auto: number;
      confirmed: number;
    };
    /** @description The holder's view. Never carries the far case, the approver or another holder. */
    GrantHeld: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      view: "HELD";
      grant_id: components["schemas"]["Uuid"];
      request_id: components["schemas"]["Uuid"];
      status: components["schemas"]["GrantStatus"];
      /** Format: date-time */
      starts_at: string;
      /** Format: date-time */
      expires_at: string;
      /** Format: date-time */
      closed_at?: string | null;
      close_cause?: components["schemas"]["GrantCloseCause"] | null;
      link_id: components["schemas"]["Uuid"];
      far_entity_id: components["schemas"]["Id"];
    };
    /** @description The approving authority's view. Never carries the link id or the far entity id of the holder's side. */
    GrantAuthority: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      view: "AUTHORITY";
      grant_id: components["schemas"]["Uuid"];
      request_id: components["schemas"]["Uuid"];
      status: components["schemas"]["GrantStatus"];
      /** Format: date-time */
      starts_at: string;
      /** Format: date-time */
      expires_at: string;
      /** Format: date-time */
      closed_at?: string | null;
      close_cause?: components["schemas"]["GrantCloseCause"] | null;
      holder: components["schemas"]["UserRef"];
      far_case_id: components["schemas"]["Id"];
    };
    /** @description The requester's view. `stub` is bound to (requester, link). Never carries the far case, the approver or a grant's authority fields. */
    AccessRequestMine: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      view: "MINE";
      request_id: components["schemas"]["Uuid"];
      status: components["schemas"]["AccessRequestStatus"];
      /** Format: date-time */
      requested_at: string;
      /**
       * Format: date-time
       * @description Seven days after the request.
       */
      expires_at: string;
      /** Format: date-time */
      decided_at?: string | null;
      decision_note?: string | null;
      stub: components["schemas"]["Stub"];
      grant?: components["schemas"]["GrantHeld"] | null;
    };
    /** @description The approver's view. `stub` is bound to (approver, link) with `near_entity_id` on the approver's side; the requester's stub id and entity are never shown. */
    AccessRequestToDecide: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      view: "TO_DECIDE";
      request_id: components["schemas"]["Uuid"];
      status: components["schemas"]["AccessRequestStatus"];
      /** Format: date-time */
      requested_at: string;
      /**
       * Format: date-time
       * @description Seven days after the request.
       */
      expires_at: string;
      /** Format: date-time */
      decided_at?: string | null;
      reason: string;
      requester: components["schemas"]["UserRef"];
      far_case_id: components["schemas"]["Id"];
      /** @description Case number of the far case, which lies in the decider's own district (SUPERVISOR) or coverage (SENIOR). No other far-case field is carried. AccessRequestMine never carries it. */
      far_case_number: string;
      stub: components["schemas"]["Stub"];
      grant?: components["schemas"]["GrantAuthority"] | null;
    };
    /** @description History under a grant: only from, to, at and reason_code, as in the explanation payload. No actor and no free text. */
    HistoryEntryGranted: {
      from: components["schemas"]["LinkState"] | null;
      to: components["schemas"]["LinkState"] | null;
      /** Format: date-time */
      at: string;
      reason_code: string | null;
    };
    /** @description Allow-listed keys only (audit spec section 3), further narrowed per event by `x-detail-keys`. Keys that carry a sequence number or chain position (`seq_from`, `seq_to`, `range_from`, `range_to`, `first_bad_seq`, `head_seq`, `anchor_seq`) are stored but never returned. Keys the reader may not see are absent, not null. */
    AuditDetail: {
      schema_version?: number;
      claimed_username?: string;
      throttled?: boolean;
      /** @description Present on every view event (audit spec section 3); true when access came from a grant. */
      via_grant?: boolean;
      failure?: string;
      claimed_sub?: string;
      case_ids?: string[];
      entity_ids?: string[];
      link_ids_shown?: components["schemas"]["Uuid"][];
      link_ids?: components["schemas"]["Uuid"][];
      stub_ids_shown?: components["schemas"]["Uuid"][];
      stub_ids?: components["schemas"]["Uuid"][];
      near_entity_ids?: string[];
      request_ids?: components["schemas"]["Uuid"][];
      grant_ids?: components["schemas"]["Uuid"][];
      change_ids?: components["schemas"]["Uuid"][];
      entity_type_filter?: string;
      action?: string;
      http_status?: number;
      run_id?: components["schemas"]["Uuid"];
      band?: components["schemas"]["Band"];
      score?: number;
      previous_state?: string;
      new_state?: string;
      cause?: string;
      stub_id?: components["schemas"]["Uuid"];
      grant_id?: components["schemas"]["Uuid"];
      /** Format: date-time */
      expires_at?: string;
      line_from?: number;
      line_to?: number;
      file_sha256?: string;
      byte_count?: number;
      document_count?: number;
      thresholds_version?: number;
      auto_count?: number;
      suggested_count?: number;
      kind?: components["schemas"]["ChangeKind"];
      subject_id?: string;
      change_hash?: string;
      old_value?: Record<string, never> | null;
      new_value?: Record<string, never>;
      case_id?: string;
      added?: boolean;
      role?: components["schemas"]["Role"];
      district_id?: components["schemas"]["Uuid"];
      filter_keys?: string[];
      result_count?: number;
      redacted?: boolean;
      /** @enum {string} */
      result?: "OK" | "BROKEN";
    };
    /** @description Provenance of one cited line. Always one of the link's two end cases. document_type, page and case_number are added by the API from the document and case rows so the panel can print 'Case, document type, page, line'; the engine omits them. */
    source: {
      case_id: string;
      document_id: string;
      line: number;
      page?: number | null;
      document_type?: string | null;
      case_number?: string | null;
    };
    gate_g1: {
      /** @constant */
      gate: "G1";
      /** @constant */
      template_key: "match.gate.below_high";
    };
    gate_g2: {
      /** @constant */
      gate: "G2";
      /** @constant */
      template_key: "match.gate.no_anchor";
    };
    gate_g3: {
      /** @constant */
      gate: "G3";
      /** @constant */
      template_key: "match.gate.single_tier";
    };
    gate_g4: {
      /** @constant */
      gate: "G4";
      /** @constant */
      template_key: "match.gate.hard_conflict";
    };
    gate_g5: {
      /** @constant */
      gate: "G5";
      /** @constant */
      template_key: "match.gate.low_extraction";
    };
    gate_g6: {
      /** @constant */
      gate: "G6";
      /** @enum {unknown} */
      template_key:
        | "match.gate.cluster_conflict"
        | "match.gate.cluster_bridge"
        | "match.gate.cluster_same_case";
    };
    gate_g7: {
      /** @constant */
      gate: "G7";
      /** @constant */
      template_key: "match.gate.org_review_only";
    };
    adjustment_cap: {
      /** @description cap - raw when raw exceeds the cap, else 0. Its own line, never merged into an item. */
      value: number;
      /** @constant */
      template_key: "match.adjust.cap";
    };
    /** @description Trap-identifier modifier. Has no sources and never says which other cases raised the flag. The identifier label for the wording comes from the item's kind. */
    modifier: {
      /** @enum {unknown} */
      code: "SHARED" | "HUB" | "MULTI_USER";
      /** @constant */
      factor: 0.2;
      /** @constant */
      template_key: "match.modifier.trap_identifier";
    };
    sources: components["schemas"]["source"][];
    item_base: {
      evidence_id: string;
      kind: string;
      strength: number;
      weight: number;
      /** @description round_half_up(weight x strength, 1); negative for opposing items. */
      contribution: number;
      /** @description True for a SHARED_* item with both attributions OWNS and trap factor 1.0 (gate G2). */
      is_anchor: boolean;
      modifiers: components["schemas"]["modifier"][];
      template_key: string;
      params: Record<string, never>;
      sources: components["schemas"]["sources"];
    };
    /**
     * @description Rendered via template key match.id_label.<code lowercase>.
     * @enum {unknown}
     */
    id_label_code: "PHONE" | "ACCOUNT" | "VEHICLE";
    p_id_exact: {
      id_label: components["schemas"]["id_label_code"];
      value: string;
    };
    i_id_exact: {
      /** @constant */
      kind?: "ID_EXACT";
      /** @constant */
      template_key?: "match.evidence.id_exact";
      params?: components["schemas"]["p_id_exact"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_phone_transposed: {
      value_a: string;
      value_b: string;
    };
    i_phone_transposed: {
      /** @constant */
      kind?: "PHONE_TRANSPOSED";
      /** @constant */
      template_key?: "match.evidence.phone_transposed";
      params?: components["schemas"]["p_phone_transposed"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    /**
     * @description Rendered via template key match.attribution.<code lowercase>.
     * @enum {unknown}
     */
    attribution_code: "OWNS" | "REGISTERED_TO" | "MENTIONED_WITH";
    p_shared_identifier: {
      value: string;
      how_a: components["schemas"]["attribution_code"];
      case_a: string;
      how_b: components["schemas"]["attribution_code"];
      case_b: string;
    };
    i_shared_phone: {
      /** @constant */
      kind?: "SHARED_PHONE";
      /** @constant */
      template_key?: "match.evidence.shared_phone";
      params?: components["schemas"]["p_shared_identifier"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    i_shared_account: {
      /** @constant */
      kind?: "SHARED_ACCOUNT";
      /** @constant */
      template_key?: "match.evidence.shared_account";
      params?: components["schemas"]["p_shared_identifier"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    i_shared_vehicle: {
      /** @constant */
      kind?: "SHARED_VEHICLE";
      /** @constant */
      template_key?: "match.evidence.shared_vehicle";
      params?: components["schemas"]["p_shared_identifier"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_name_sim: {
      name_a: string;
      name_b: string;
      sim: number;
    };
    i_per_name_sim: {
      /** @constant */
      kind?: "PER_NAME_SIM";
      /** @constant */
      template_key?: "match.evidence.per_name_sim";
      params?: components["schemas"]["p_name_sim"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_relative: {
      rel_a: string;
      rel_b: string;
    };
    i_per_relative_name: {
      /** @constant */
      kind?: "PER_RELATIVE_NAME";
      /** @constant */
      template_key?: "match.evidence.per_relative_name";
      params?: components["schemas"]["p_relative"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    /** Format: date */
    iso_date: string;
    p_dob_match: {
      dob: components["schemas"]["iso_date"];
    };
    i_per_dob_match: {
      /** @constant */
      kind?: "PER_DOB_MATCH";
      /** @constant */
      template_key?: "match.evidence.per_dob_match";
      params?: components["schemas"]["p_dob_match"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_age_pair: {
      age_a: number;
      age_b: number;
    };
    i_per_age_close: {
      /** @constant */
      kind?: "PER_AGE_CLOSE";
      /** @constant */
      template_key?: "match.evidence.per_age_close";
      params?: components["schemas"]["p_age_pair"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_locality: {
      place: string;
    };
    i_per_locality: {
      /** @constant */
      kind?: "PER_LOCALITY";
      /** @constant */
      template_key?: "match.evidence.per_locality";
      params?: components["schemas"]["p_locality"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_none: Record<string, never>;
    i_per_near_phone: {
      /** @constant */
      kind?: "PER_NEAR_PHONE";
      /** @constant */
      template_key?: "match.evidence.per_near_phone";
      params?: components["schemas"]["p_none"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_network: {
      k: number;
      list: string[];
    };
    i_per_shared_network: {
      /** @constant */
      kind?: "PER_SHARED_NETWORK";
      /** @constant */
      template_key?: "match.evidence.per_shared_network";
      params?: components["schemas"]["p_network"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_co_location: {
      k: number;
    };
    i_per_co_location: {
      /** @constant */
      kind?: "PER_CO_LOCATION";
      /** @constant */
      template_key?: "match.evidence.per_co_location";
      params?: components["schemas"]["p_co_location"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_org_name_sim: {
      name_a: string;
      name_b: string;
    };
    i_org_name_sim: {
      /** @constant */
      kind?: "ORG_NAME_SIM";
      /** @constant */
      template_key?: "match.evidence.org_name_sim";
      params?: components["schemas"]["p_org_name_sim"];
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    support_item:
      | components["schemas"]["i_id_exact"]
      | components["schemas"]["i_phone_transposed"]
      | components["schemas"]["i_shared_phone"]
      | components["schemas"]["i_shared_account"]
      | components["schemas"]["i_shared_vehicle"]
      | components["schemas"]["i_per_name_sim"]
      | components["schemas"]["i_per_relative_name"]
      | components["schemas"]["i_per_dob_match"]
      | components["schemas"]["i_per_age_close"]
      | components["schemas"]["i_per_locality"]
      | components["schemas"]["i_per_near_phone"]
      | components["schemas"]["i_per_shared_network"]
      | components["schemas"]["i_per_co_location"]
      | components["schemas"]["i_org_name_sim"];
    p_bank_conflict: {
      bank_a: string;
      bank_b: string;
    };
    a_acct_bank_conflict: {
      /** @constant */
      kind?: "ACCT_BANK_CONFLICT";
      /** @constant */
      template_key?: "match.evidence.acct_bank_conflict";
      params?: components["schemas"]["p_bank_conflict"];
      /** @constant */
      severity: "veto";
      /** @constant */
      weight?: 0;
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    p_dob_pair: {
      dob_a: components["schemas"]["iso_date"];
      dob_b: components["schemas"]["iso_date"];
    };
    a_per_dob_conflict: {
      /** @constant */
      kind?: "PER_DOB_CONFLICT";
      /** @constant */
      template_key?: "match.evidence.per_dob_conflict";
      params?: components["schemas"]["p_dob_pair"];
      /** @constant */
      severity: "hard";
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    a_per_dob_mismatch: {
      /** @constant */
      kind?: "PER_DOB_MISMATCH";
      /** @constant */
      template_key?: "match.evidence.per_dob_mismatch";
      params?: components["schemas"]["p_dob_pair"];
      /** @constant */
      severity: "soft";
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    a_per_age_conflict: {
      /** @constant */
      kind?: "PER_AGE_CONFLICT";
      /** @constant */
      template_key?: "match.evidence.per_age_conflict";
      params?: components["schemas"]["p_age_pair"];
      /**
       * @description Hard when the ages differ by more than 10 years (weight 40), else soft (weight 20).
       * @enum {unknown}
       */
      severity: "soft" | "hard";
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    a_per_gender_conflict: {
      /** @constant */
      kind?: "PER_GENDER_CONFLICT";
      /** @constant */
      template_key?: "match.evidence.per_gender_conflict";
      params?: components["schemas"]["p_none"];
      /** @constant */
      severity: "hard";
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    a_per_relative_conflict: {
      /** @constant */
      kind?: "PER_RELATIVE_CONFLICT";
      /** @constant */
      template_key?: "match.evidence.per_relative_conflict";
      params?: components["schemas"]["p_relative"];
      /** @constant */
      severity: "soft";
      contribution?: unknown;
    } & components["schemas"]["item_base"];
    /** @enum {unknown} */
    link_state: "AUTO" | "SUGGESTED" | "CONFIRMED" | "REJECTED" | "UNDONE";
    uuid: string;
    score: number;
    failed_gate:
      | components["schemas"]["gate_g1"]
      | components["schemas"]["gate_g2"]
      | components["schemas"]["gate_g3"]
      | components["schemas"]["gate_g4"]
      | components["schemas"]["gate_g5"]
      | components["schemas"]["gate_g6"]
      | components["schemas"]["gate_g7"];
    record: {
      entity_id: string;
      case_id: string;
      raw_text: string;
      normalized: string;
      extraction_confidence: number;
      source: components["schemas"]["source"];
    };
    tier: {
      /** @enum {unknown} */
      tier: 1 | 2 | 3;
      cap: number;
      /** @description Sum of item contributions in this tier, before the cap. */
      raw: number;
      cap_adjustment: components["schemas"]["adjustment_cap"];
      /** @description raw + cap_adjustment.value. */
      subtotal: number;
      items: components["schemas"]["support_item"][];
    };
    against_item:
      | components["schemas"]["a_acct_bank_conflict"]
      | components["schemas"]["a_per_dob_conflict"]
      | components["schemas"]["a_per_dob_mismatch"]
      | components["schemas"]["a_per_age_conflict"]
      | components["schemas"]["a_per_gender_conflict"]
      | components["schemas"]["a_per_relative_conflict"];
    adjustment_clamp: {
      /** @description clamp(S_raw, 0, 100) - S_raw. */
      value: number;
      /** @constant */
      template_key: "match.adjust.clamp";
    };
    history_entry: {
      from: components["schemas"]["link_state"] | null;
      /** @description Null only for WITHDRAWN, which removes the edge. */
      to: components["schemas"]["link_state"] | null;
      /** Format: date-time */
      at: string;
      /** @description DEMOTED, PROMOTED, WITHDRAWN for engine transitions; null for a first creation or a human decision. */
      reason_code: string | null;
    };
    /**
     * TraceX link explanation payload
     * @description Why two entities were linked (docs/specs/engine-matching.md section 7). Carries codes, numbers, ids and values only: no wording. Clients render every line from template_key plus params; wording lives in the shared i18n files (en, hi). Produced by the engine, stored on the link, served by GET /links/{link_id}/explanation after the access check. Invariant, tested by exact decimal equality: sum(support[].subtotal) + sum(against[].contribution) + clamp_adjustment.value = score, where subtotal = raw + cap_adjustment.value. A non-numeric `weight` never occurs; a veto item carries weight 0 and contribution 0. Identifier values in params may be masked by the API (masking rules are the API's, see docs/architecture.md); the schema treats them as opaque strings. Tiers with no items may be omitted (an identifier pair has tiers 1 and 2 at most; AC-02 has only tier 1), so clients must not expect three tier blocks. When the caller may not read the source lines of a case, the API masks PHONE and ACCOUNT values in every param, `raw_text` and `normalized`, and sets `masked` true; the full value then appears nowhere in the payload (access spec section 4.1).
     */
    "explanation.schema": {
      /** @description Opaque random id of the link; never derived from entity, case or run ids. */
      link_id: components["schemas"]["uuid"];
      /** @enum {unknown} */
      entity_type: "PERSON" | "ORG" | "PHONE" | "ACCOUNT" | "VEHICLE";
      state: components["schemas"]["link_state"];
      /** @description Composite score 0 to 100, one decimal, after caps and clamp. */
      score: components["schemas"]["score"];
      /**
       * @description LOW is possible only for a link that a human reopened or confirmed after thresholds moved; the engine never stores a new Low pair.
       * @enum {unknown}
       */
      band: "HIGH" | "MEDIUM" | "LOW";
      thresholds: {
        high_min: number;
        medium_min: number;
        thresholds_version: number;
      };
      ruleset_version: string;
      gates: {
        /** @description True only when every gate for this entity type passed (the AUTO condition). */
        passed: boolean;
        failed: components["schemas"]["failed_gate"][];
      };
      /** @description The two end entities as extracted. Never a third case. */
      records: components["schemas"]["record"][];
      /** @description Supporting evidence grouped by tier, ascending, omitting tiers without items. Identifier pairs use tiers 1 and 2 only; PERSON and ORG pairs may use 1 to 3. */
      support: components["schemas"]["tier"][];
      /** @description Opposing evidence. Empty when nothing disagrees. */
      against: components["schemas"]["against_item"][];
      clamp_adjustment: components["schemas"]["adjustment_clamp"];
      /** @description Only from, to, at and reason_code. The actor and the free-text reason stay on the link history and are never in this payload. */
      history: components["schemas"]["history_entry"][];
      /** @description Added by the API, never by the engine: true when any value in this payload was masked. */
      masked?: boolean;
      $defs: {
        uuid: string;
        score: number;
        /** @enum {unknown} */
        link_state: "AUTO" | "SUGGESTED" | "CONFIRMED" | "REJECTED" | "UNDONE";
        /**
         * @description Rendered via template key match.attribution.<code lowercase>.
         * @enum {unknown}
         */
        attribution_code: "OWNS" | "REGISTERED_TO" | "MENTIONED_WITH";
        /**
         * @description Rendered via template key match.id_label.<code lowercase>.
         * @enum {unknown}
         */
        id_label_code: "PHONE" | "ACCOUNT" | "VEHICLE";
        /** Format: date */
        iso_date: string;
        /** @description Provenance of one cited line. Always one of the link's two end cases. document_type, page and case_number are added by the API from the document and case rows so the panel can print 'Case, document type, page, line'; the engine omits them. */
        source: {
          case_id: string;
          document_id: string;
          line: number;
          page?: number | null;
          document_type?: string | null;
          case_number?: string | null;
        };
        sources: components["schemas"]["source"][];
        record: {
          entity_id: string;
          case_id: string;
          raw_text: string;
          normalized: string;
          extraction_confidence: number;
          source: components["schemas"]["source"];
        };
        failed_gate:
          | components["schemas"]["gate_g1"]
          | components["schemas"]["gate_g2"]
          | components["schemas"]["gate_g3"]
          | components["schemas"]["gate_g4"]
          | components["schemas"]["gate_g5"]
          | components["schemas"]["gate_g6"]
          | components["schemas"]["gate_g7"];
        gate_g1: {
          /** @constant */
          gate: "G1";
          /** @constant */
          template_key: "match.gate.below_high";
        };
        gate_g2: {
          /** @constant */
          gate: "G2";
          /** @constant */
          template_key: "match.gate.no_anchor";
        };
        gate_g3: {
          /** @constant */
          gate: "G3";
          /** @constant */
          template_key: "match.gate.single_tier";
        };
        gate_g4: {
          /** @constant */
          gate: "G4";
          /** @constant */
          template_key: "match.gate.hard_conflict";
        };
        gate_g5: {
          /** @constant */
          gate: "G5";
          /** @constant */
          template_key: "match.gate.low_extraction";
        };
        gate_g6: {
          /** @constant */
          gate: "G6";
          /** @enum {unknown} */
          template_key:
            | "match.gate.cluster_conflict"
            | "match.gate.cluster_bridge"
            | "match.gate.cluster_same_case";
        };
        gate_g7: {
          /** @constant */
          gate: "G7";
          /** @constant */
          template_key: "match.gate.org_review_only";
        };
        adjustment_cap: {
          /** @description cap - raw when raw exceeds the cap, else 0. Its own line, never merged into an item. */
          value: number;
          /** @constant */
          template_key: "match.adjust.cap";
        };
        adjustment_clamp: {
          /** @description clamp(S_raw, 0, 100) - S_raw. */
          value: number;
          /** @constant */
          template_key: "match.adjust.clamp";
        };
        tier: {
          /** @enum {unknown} */
          tier: 1 | 2 | 3;
          cap: number;
          /** @description Sum of item contributions in this tier, before the cap. */
          raw: number;
          cap_adjustment: components["schemas"]["adjustment_cap"];
          /** @description raw + cap_adjustment.value. */
          subtotal: number;
          items: components["schemas"]["support_item"][];
        };
        /** @description Trap-identifier modifier. Has no sources and never says which other cases raised the flag. The identifier label for the wording comes from the item's kind. */
        modifier: {
          /** @enum {unknown} */
          code: "SHARED" | "HUB" | "MULTI_USER";
          /** @constant */
          factor: 0.2;
          /** @constant */
          template_key: "match.modifier.trap_identifier";
        };
        item_base: {
          evidence_id: string;
          kind: string;
          strength: number;
          weight: number;
          /** @description round_half_up(weight x strength, 1); negative for opposing items. */
          contribution: number;
          /** @description True for a SHARED_* item with both attributions OWNS and trap factor 1.0 (gate G2). */
          is_anchor: boolean;
          modifiers: components["schemas"]["modifier"][];
          template_key: string;
          params: Record<string, never>;
          sources: components["schemas"]["sources"];
        };
        support_item:
          | components["schemas"]["i_id_exact"]
          | components["schemas"]["i_phone_transposed"]
          | components["schemas"]["i_shared_phone"]
          | components["schemas"]["i_shared_account"]
          | components["schemas"]["i_shared_vehicle"]
          | components["schemas"]["i_per_name_sim"]
          | components["schemas"]["i_per_relative_name"]
          | components["schemas"]["i_per_dob_match"]
          | components["schemas"]["i_per_age_close"]
          | components["schemas"]["i_per_locality"]
          | components["schemas"]["i_per_near_phone"]
          | components["schemas"]["i_per_shared_network"]
          | components["schemas"]["i_per_co_location"]
          | components["schemas"]["i_org_name_sim"];
        against_item:
          | components["schemas"]["a_acct_bank_conflict"]
          | components["schemas"]["a_per_dob_conflict"]
          | components["schemas"]["a_per_dob_mismatch"]
          | components["schemas"]["a_per_age_conflict"]
          | components["schemas"]["a_per_gender_conflict"]
          | components["schemas"]["a_per_relative_conflict"];
        p_id_exact: {
          id_label: components["schemas"]["id_label_code"];
          value: string;
        };
        p_phone_transposed: {
          value_a: string;
          value_b: string;
        };
        p_shared_identifier: {
          value: string;
          how_a: components["schemas"]["attribution_code"];
          case_a: string;
          how_b: components["schemas"]["attribution_code"];
          case_b: string;
        };
        p_name_sim: {
          name_a: string;
          name_b: string;
          sim: number;
        };
        p_org_name_sim: {
          name_a: string;
          name_b: string;
        };
        p_relative: {
          rel_a: string;
          rel_b: string;
        };
        p_dob_match: {
          dob: components["schemas"]["iso_date"];
        };
        p_dob_pair: {
          dob_a: components["schemas"]["iso_date"];
          dob_b: components["schemas"]["iso_date"];
        };
        p_age_pair: {
          age_a: number;
          age_b: number;
        };
        p_locality: {
          place: string;
        };
        p_none: Record<string, never>;
        p_network: {
          k: number;
          list: string[];
        };
        p_co_location: {
          k: number;
        };
        p_bank_conflict: {
          bank_a: string;
          bank_b: string;
        };
        i_id_exact: {
          /** @constant */
          kind?: "ID_EXACT";
          /** @constant */
          template_key?: "match.evidence.id_exact";
          params?: components["schemas"]["p_id_exact"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_phone_transposed: {
          /** @constant */
          kind?: "PHONE_TRANSPOSED";
          /** @constant */
          template_key?: "match.evidence.phone_transposed";
          params?: components["schemas"]["p_phone_transposed"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_shared_phone: {
          /** @constant */
          kind?: "SHARED_PHONE";
          /** @constant */
          template_key?: "match.evidence.shared_phone";
          params?: components["schemas"]["p_shared_identifier"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_shared_account: {
          /** @constant */
          kind?: "SHARED_ACCOUNT";
          /** @constant */
          template_key?: "match.evidence.shared_account";
          params?: components["schemas"]["p_shared_identifier"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_shared_vehicle: {
          /** @constant */
          kind?: "SHARED_VEHICLE";
          /** @constant */
          template_key?: "match.evidence.shared_vehicle";
          params?: components["schemas"]["p_shared_identifier"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_name_sim: {
          /** @constant */
          kind?: "PER_NAME_SIM";
          /** @constant */
          template_key?: "match.evidence.per_name_sim";
          params?: components["schemas"]["p_name_sim"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_relative_name: {
          /** @constant */
          kind?: "PER_RELATIVE_NAME";
          /** @constant */
          template_key?: "match.evidence.per_relative_name";
          params?: components["schemas"]["p_relative"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_dob_match: {
          /** @constant */
          kind?: "PER_DOB_MATCH";
          /** @constant */
          template_key?: "match.evidence.per_dob_match";
          params?: components["schemas"]["p_dob_match"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_age_close: {
          /** @constant */
          kind?: "PER_AGE_CLOSE";
          /** @constant */
          template_key?: "match.evidence.per_age_close";
          params?: components["schemas"]["p_age_pair"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_locality: {
          /** @constant */
          kind?: "PER_LOCALITY";
          /** @constant */
          template_key?: "match.evidence.per_locality";
          params?: components["schemas"]["p_locality"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_near_phone: {
          /** @constant */
          kind?: "PER_NEAR_PHONE";
          /** @constant */
          template_key?: "match.evidence.per_near_phone";
          params?: components["schemas"]["p_none"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_shared_network: {
          /** @constant */
          kind?: "PER_SHARED_NETWORK";
          /** @constant */
          template_key?: "match.evidence.per_shared_network";
          params?: components["schemas"]["p_network"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_per_co_location: {
          /** @constant */
          kind?: "PER_CO_LOCATION";
          /** @constant */
          template_key?: "match.evidence.per_co_location";
          params?: components["schemas"]["p_co_location"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        i_org_name_sim: {
          /** @constant */
          kind?: "ORG_NAME_SIM";
          /** @constant */
          template_key?: "match.evidence.org_name_sim";
          params?: components["schemas"]["p_org_name_sim"];
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        a_acct_bank_conflict: {
          /** @constant */
          kind?: "ACCT_BANK_CONFLICT";
          /** @constant */
          template_key?: "match.evidence.acct_bank_conflict";
          params?: components["schemas"]["p_bank_conflict"];
          /** @constant */
          severity: "veto";
          /** @constant */
          weight?: 0;
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        a_per_dob_conflict: {
          /** @constant */
          kind?: "PER_DOB_CONFLICT";
          /** @constant */
          template_key?: "match.evidence.per_dob_conflict";
          params?: components["schemas"]["p_dob_pair"];
          /** @constant */
          severity: "hard";
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        a_per_dob_mismatch: {
          /** @constant */
          kind?: "PER_DOB_MISMATCH";
          /** @constant */
          template_key?: "match.evidence.per_dob_mismatch";
          params?: components["schemas"]["p_dob_pair"];
          /** @constant */
          severity: "soft";
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        a_per_age_conflict: {
          /** @constant */
          kind?: "PER_AGE_CONFLICT";
          /** @constant */
          template_key?: "match.evidence.per_age_conflict";
          params?: components["schemas"]["p_age_pair"];
          /**
           * @description Hard when the ages differ by more than 10 years (weight 40), else soft (weight 20).
           * @enum {unknown}
           */
          severity: "soft" | "hard";
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        a_per_gender_conflict: {
          /** @constant */
          kind?: "PER_GENDER_CONFLICT";
          /** @constant */
          template_key?: "match.evidence.per_gender_conflict";
          params?: components["schemas"]["p_none"];
          /** @constant */
          severity: "hard";
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        a_per_relative_conflict: {
          /** @constant */
          kind?: "PER_RELATIVE_CONFLICT";
          /** @constant */
          template_key?: "match.evidence.per_relative_conflict";
          params?: components["schemas"]["p_relative"];
          /** @constant */
          severity: "soft";
          contribution?: unknown;
        } & components["schemas"]["item_base"];
        history_entry: {
          from: components["schemas"]["link_state"] | null;
          /** @description Null only for WITHDRAWN, which removes the edge. */
          to: components["schemas"]["link_state"] | null;
          /** Format: date-time */
          at: string;
          /** @description DEMOTED, PROMOTED, WITHDRAWN for engine transitions; null for a first creation or a human decision. */
          reason_code: string | null;
        };
      };
    } & (unknown & unknown & unknown);
  };
  responses: {
    /** @description Missing, malformed, expired or badly signed token, stale `ver`, dead session, or bad credentials. Audited (AUTH_TOKEN_REJECTED or AUTH_LOGIN_FAILED). */
    Unauthorized: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "UNAUTHENTICATED",
         *       "message_key": "error.unauthenticated"
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
    /** @description The caller can see the thing but their role does not permit the action. Audited (ACCESS_DENIED). Never used to hide that something exists. */
    Forbidden: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "FORBIDDEN",
         *       "message_key": "error.forbidden"
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
    /** @description Unknown or not visible to the caller. Body and headers are identical for both. Audited (ACCESS_DENIED, target UNRESOLVED, no case reference). */
    NotFound: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "NOT_FOUND",
         *       "message_key": "error.not_found"
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
    /** @description The state does not allow it (invalid transition, stale hash, cooldown, last approver, run in progress). */
    Conflict: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "INVALID_TRANSITION",
         *       "message_key": "error.invalid_transition"
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
    /** @description Input invalid, including a bad or foreign cursor. */
    Unprocessable: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "VALIDATION_FAILED",
         *       "message_key": "error.validation_failed",
         *       "field_errors": [
         *         {
         *           "field": "reason",
         *           "code": "too_short"
         *         }
         *       ]
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
    /** @description The audit chain does not verify, or has not been verified yet, so the API is paused for safety. Every route except `GET /health`, `GET /ready` and `POST /audit/verify` answers this until a verify passes. The body is fixed, carries no data, and the client shows the safety-pause message. */
    SafetyPause: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "NOT_READY",
         *       "message_key": "error.not_ready"
         *     }
         */
        "application/json": components["schemas"]["SafetyPauseError"];
      };
    };
    /** @description Login throttled (5 failures per username string and IP in 15 minutes), applied whether or not the username exists. */
    TooManyRequests: {
      headers: {
        /** @description Seconds until sign-in may be tried again. */
        "Retry-After"?: number;
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "TOO_MANY_REQUESTS",
         *       "message_key": "error.too_many_requests"
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
    /** @description Includes failure to append the audit row (fail closed): no data is returned. */
    ServerError: {
      headers: {
        [name: string]: unknown;
      };
      content: {
        /**
         * @example {
         *       "code": "INTERNAL",
         *       "message_key": "error.internal"
         *     }
         */
        "application/json": components["schemas"]["Error"];
      };
    };
  };
  parameters: {
    Limit: number;
    /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
    Cursor: components["schemas"]["Cursor"];
    CaseId: components["schemas"]["Id"];
    EntityId: components["schemas"]["Id"];
    LinkId: components["schemas"]["Uuid"];
    StubId: components["schemas"]["Uuid"];
    RequestId: components["schemas"]["Uuid"];
    GrantId: components["schemas"]["Uuid"];
    BatchId: components["schemas"]["Uuid"];
    RunId: components["schemas"]["Uuid"];
    UserId: components["schemas"]["Uuid"];
    ChangeId: components["schemas"]["Uuid"];
  };
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  getHealth: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Process is up. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HealthStatus"];
        };
      };
    };
  };
  getReady: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Ready. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HealthStatus"];
        };
      };
      /** @description Not ready. Body is the fixed `NOT_READY` error (the same body as the safety pause). */
      503: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SafetyPauseError"];
        };
      };
    };
  };
  login: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LoginRequest"];
      };
    };
    responses: {
      /** @description Signed in. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TokenPair"];
        };
      };
      401: components["responses"]["Unauthorized"];
      422: components["responses"]["Unprocessable"];
      429: components["responses"]["TooManyRequests"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  refreshToken: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RefreshRequest"];
      };
    };
    responses: {
      /** @description New token pair. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TokenPair"];
        };
      };
      401: components["responses"]["Unauthorized"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  logout: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Signed out. */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      401: components["responses"]["Unauthorized"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getMe: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The caller. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["User"];
        };
      };
      401: components["responses"]["Unauthorized"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listCases: {
    parameters: {
      query?: {
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
        /** @description Prefix match on the case number (officer app search). */
        case_number?: string;
        district_id?: components["schemas"]["Uuid"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of cases. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CasePage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listCaseEntities: {
    parameters: {
      query?: {
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
        type?: components["schemas"]["EntityType"];
      };
      header?: never;
      path: {
        case_id: components["parameters"]["CaseId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The case and a page of its entities. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CaseEntitiesPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getEntity: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        entity_id: components["parameters"]["EntityId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The entity. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntityDetail"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  searchEntities: {
    parameters: {
      query: {
        q: string;
        type?: components["schemas"]["EntityType"];
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Matching entities. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntityPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getSourceLines: {
    parameters: {
      query: {
        line_from: number;
        line_to: number;
      };
      header?: never;
      path: {
        document_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The requested lines (at most 200). */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SourceLines"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listLinks: {
    parameters: {
      query?: {
        /** @description Only links touching this entity (must be visible, else 404). */
        entity_id?: components["schemas"]["Id"];
        state?: components["schemas"]["LinkState"];
        entity_type?: components["schemas"]["EntityType"];
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of links and stubs. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getLink: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        link_id: components["parameters"]["LinkId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The link. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkDetail"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getLinkExplanation: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        link_id: components["parameters"]["LinkId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The explanation. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["explanation.schema"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  confirmLink: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        link_id: components["parameters"]["LinkId"];
      };
      cookie?: never;
    };
    requestBody?: {
      content: {
        "application/json": components["schemas"]["ConfirmLinkRequest"];
      };
    };
    responses: {
      /** @description The link after the decision. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkDetail"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  rejectLink: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        link_id: components["parameters"]["LinkId"];
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LinkReasonRequest"];
      };
    };
    responses: {
      /** @description The link after the decision. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkDetail"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  undoLink: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        link_id: components["parameters"]["LinkId"];
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LinkReasonRequest"];
      };
    };
    responses: {
      /** @description The link after the decision. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkDetail"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  reopenLink: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        link_id: components["parameters"]["LinkId"];
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LinkReasonRequest"];
      };
    };
    responses: {
      /** @description The link after the decision. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkDetail"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listReviewQueue: {
    parameters: {
      query?: {
        /** @description SUGGESTED is Waiting, REJECTED and UNDONE are the decided links open to reopen (D34, D43). */
        state?: "SUGGESTED" | "REJECTED" | "UNDONE";
        entity_type?: components["schemas"]["EntityType"];
        district_id?: components["schemas"]["Uuid"];
        /** @description Only links waiting at least this many days. */
        waiting_days_min?: number;
        sort?: "waiting_since" | "score" | "entity_type";
        order?: "asc" | "desc";
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of queue items. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ReviewQueuePage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getEntityGraph: {
    parameters: {
      query?: {
        depth?: number;
        limit?: number;
      };
      header?: never;
      path: {
        entity_id: components["parameters"]["EntityId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The neighbourhood. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GraphResponse"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getEntityCluster: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        entity_id: components["parameters"]["EntityId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The cluster for this viewer. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ClusterResponse"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getEntityPaths: {
    parameters: {
      query?: {
        max_hops?: number;
        limit?: number;
      };
      header?: never;
      path: {
        entity_id: components["parameters"]["EntityId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The paths for this viewer. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PathsResponse"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getStub: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        stub_id: components["parameters"]["StubId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The stub. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Stub"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listAccessRequests: {
    parameters: {
      query: {
        scope: "mine" | "to_decide";
        status?: components["schemas"]["AccessRequestStatus"];
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of requests. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AccessRequestPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  createAccessRequest: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateAccessRequest"];
      };
    };
    responses: {
      /** @description Request created, status PENDING. */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AccessRequestMine"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getAccessRequest: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        request_id: components["parameters"]["RequestId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The request. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AccessRequest"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  withdrawAccessRequest: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        request_id: components["parameters"]["RequestId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The request, now WITHDRAWN. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AccessRequestMine"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  approveAccessRequest: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        request_id: components["parameters"]["RequestId"];
      };
      cookie?: never;
    };
    requestBody?: {
      content: {
        "application/json": components["schemas"]["ApproveAccessRequest"];
      };
    };
    responses: {
      /** @description The approved request with its grant. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AccessRequestToDecide"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  denyAccessRequest: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        request_id: components["parameters"]["RequestId"];
      };
      cookie?: never;
    };
    requestBody?: {
      content: {
        "application/json": components["schemas"]["DenyAccessRequest"];
      };
    };
    responses: {
      /** @description The request, now DENIED. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AccessRequestToDecide"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listGrants: {
    parameters: {
      query: {
        scope: "held" | "authority";
        status?: components["schemas"]["GrantStatus"];
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of grants. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GrantPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getGrant: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        grant_id: components["parameters"]["GrantId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The grant. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Grant"];
        };
      };
      401: components["responses"]["Unauthorized"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  revokeGrant: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        grant_id: components["parameters"]["GrantId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The grant, now REVOKED. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GrantAuthority"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listUploads: {
    parameters: {
      query?: {
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of batches. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UploadBatchPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  uploadFiles: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "multipart/form-data": components["schemas"]["UploadRequest"];
      };
    };
    responses: {
      /** @description Accepted, one batch per file. */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UploadResponse"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getUpload: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        batch_id: components["parameters"]["BatchId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The batch. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UploadBatch"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listMatchingRuns: {
    parameters: {
      query?: {
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of runs. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MatchRunPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  startMatchingRun: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: {
      content: {
        "application/json": components["schemas"]["StartRunRequest"];
      };
    };
    responses: {
      /** @description Run started. */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MatchRun"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getMatchingRun: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        run_id: components["parameters"]["RunId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The run. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MatchRun"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listJurisdictions: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description All states with districts. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JurisdictionList"];
        };
      };
      401: components["responses"]["Unauthorized"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listRoles: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The roles. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RoleList"];
        };
      };
      401: components["responses"]["Unauthorized"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listUsers: {
    parameters: {
      query?: {
        role?: components["schemas"]["Role"];
        active?: boolean;
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of users. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getUser: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: components["parameters"]["UserId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The user. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["User"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getThresholds: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Current thresholds. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Thresholds"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listPendingChanges: {
    parameters: {
      query?: {
        state?: components["schemas"]["ChangeState"];
        kind?: components["schemas"]["ChangeKind"];
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of changes. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PendingChangePage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  proposeChange: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ProposeChangeRequest"];
      };
    };
    responses: {
      /** @description Proposal recorded, state PENDING. */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PendingChange"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  getPendingChange: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        change_id: components["parameters"]["ChangeId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The change. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PendingChange"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  approveChange: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        change_id: components["parameters"]["ChangeId"];
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ApproveChangeRequest"];
      };
    };
    responses: {
      /** @description The change, now APPROVED and applied. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PendingChange"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  denyChange: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        change_id: components["parameters"]["ChangeId"];
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description The change, now DENIED. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PendingChange"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      404: components["responses"]["NotFound"];
      409: components["responses"]["Conflict"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  listAudit: {
    parameters: {
      query?: {
        event_type?: components["schemas"]["AuditEventType"];
        outcome?: "SUCCESS" | "DENIED" | "FAILED";
        actor_user_id?: components["schemas"]["Uuid"];
        case_id?: string;
        target_id?: string;
        occurred_from?: string;
        occurred_to?: string;
        /** @description Visible fields only. */
        sort?: "occurred_at" | "event_type" | "outcome";
        order?: "asc" | "desc";
        limit?: components["parameters"]["Limit"];
        /** @description Opaque paging cursor from a previous response. Encrypted, bound to the reader and filters, expires after 15 minutes; any mismatch is 422 `VALIDATION_FAILED`. */
        cursor?: components["parameters"]["Cursor"];
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description A page of audit rows the reader may see. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AuditPage"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      422: components["responses"]["Unprocessable"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
  verifyAuditChain: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Verification result. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AuditVerifyResult"];
        };
      };
      401: components["responses"]["Unauthorized"];
      403: components["responses"]["Forbidden"];
      500: components["responses"]["ServerError"];
    };
  };
  getLinkTotals: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Totals. */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LinkTotals"];
        };
      };
      401: components["responses"]["Unauthorized"];
      /** @description Any non-ADMIN caller. */
      404: components["responses"]["NotFound"];
      500: components["responses"]["ServerError"];
      503: components["responses"]["SafetyPause"];
    };
  };
}
