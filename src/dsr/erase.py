"""Contracts for the DSR account-erasure engine.

Storage model
    store maps a physical storage name to a mapping of user id to user data.
    Keys starting with two underscores are reserved engine metadata and are
    never treated as user data:
        __tombstones__  user id to tombstone metadata
        __requests__    user id to accepted request metadata
        __cascades__    user id to latest cascade outcome

Policy model
    deadline_seconds          int, service deadline after acceptance
    targets                   list of storage names to cascade and recheck
    tombstone                 bool, tombstone control is required
    cascade                   bool, cascading deletion is required
    residual_check            bool, post-delete residual check is required
    backup_retention_seconds  int, minimum backup age before deletion

Time is always an integer epoch second supplied by the caller. The engine
never reads the clock and never uses randomness. Tolerance 0: a storage,
target or backup is not cleared unless the engine observes and confirms it.
"""


def accept_request(store, user, kind, now, policy) -> dict:
    """Accept a request and attach its absolute deadline.

    Reject a user whose tombstone exists with PermissionError, including a
    normal write request after erasure. Compute deadline as now plus
    policy["deadline_seconds"]; no grace period is allowed. Store metadata
    at store["__requests__"][user] and return a dict containing user, kind,
    accepted_at, deadline and status accepted. Tolerance 0.
    """
    raise NotImplementedError


def tombstone(store, user, now) -> dict:
    """Create an irreversible tombstone at now.

    Store user, at and state tombstoned under store["__tombstones__"]. The
    first timestamp wins: repeated calls are idempotent and a later ordinary
    write must not replace or refresh the marker. Return the stored tombstone
    dict. Tolerance 0 for writes after erasure.
    """
    raise NotImplementedError


def cascade(store, user, targets) -> dict:
    """Delete user from every target and confirm each result.

    For each target, remove the user key, read the target again and confirm
    the key is absent. A target that is missing, unreadable or still holds
    the user is confirmed False and complete False. Return user, a targets
    map of name to deleted and confirmed booleans, and complete. Record the
    outcome at store["__cascades__"][user]. Never treat an unconfirmed target
    as a success. Tolerance 0.
    """
    raise NotImplementedError


def verify_gone(store, user) -> list[str]:
    """Return every storage still holding a record for user.

    Scan every non-reserved storage in store, including cache and search
    indexes, not just the primary store. Return names in storage insertion
    order; an empty list means fully erased. Unreadable storage counts as a
    residual. Tolerance 0.
    """
    raise NotImplementedError


def backup_policy(backup, policy) -> bool:
    """Return True only when a backup has reached its retention age.

    backup has created_at and now epoch seconds. Read the retention period
    from policy["backup_retention_seconds"] and allow deletion only when
    now minus created_at is greater than or equal to that period. Return
    False before expiry. Do not mutate backup. Invalid timestamps are an
    error, not permission to delete. Tolerance 0.
    """
    raise NotImplementedError


def report(store, user, now) -> dict:
    """Build a report that exposes timing and partial completion.

    Read request metadata from store["__requests__"] and cascade metadata
    from store["__cascades__"]. Return user, status, deadline,
    elapsed_seconds, within_deadline, completed_targets, failed_targets and
    tombstoned. elapsed_seconds is now minus accepted_at. status is complete
    only when every target is confirmed and verify_gone returns empty;
    otherwise it is partial. within_deadline is now less than or equal to
    deadline. Never omit elapsed time or hide a partial result. Tolerance 0.
    """
    raise NotImplementedError


def validate_policy(policy) -> list[str]:
    """Return missing control names in a fixed order.

    Check policy["tombstone"], policy["cascade"] and
    policy["residual_check"]. A missing or falsy value yields tombstone,
    cascade or residual_check respectively, in that order. A complete policy
    returns an empty list. There are no implicit defaults: absence is an
    issue. Tolerance 0.
    """
    raise NotImplementedError


def dsr_batch(requests, policy, now) -> dict:
    """Process independent requests in order.

    Each request is a store mapping, a user id and a kind, and owns its own
    tombstone state. For each request accept it, tombstone the user, cascade
    over policy["targets"], verify and report. Return results with user and
    status plus a complete flag; a successful request has status complete,
    and an exception in one request becomes status error without affecting
    the next. Never reuse one user's tombstone for another user. Tolerance 0.
    """
    raise NotImplementedError