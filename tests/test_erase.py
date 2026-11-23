import pytest

from dsr.erase import (
    accept_request,
    backup_policy,
    cascade,
    dsr_batch,
    report,
    tombstone,
    validate_policy,
    verify_gone,
)


NOW = 1_700_000_000
DAY = 86_400


def test_defect_01_accept_request_records_deadline(store, policy):
    accepted = accept_request(store, "alice", "erasure", NOW, policy)
    expected_deadline = NOW + policy["deadline_seconds"]
    assert accepted["accepted_at"] == NOW
    assert accepted["deadline"] == expected_deadline
    assert store["__requests__"]["alice"]["deadline"] == expected_deadline


def test_normal_accept_and_erase_succeeds(store, policy):
    accepted = accept_request(store, "alice", "erasure", NOW, policy)
    marker = tombstone(store, "alice", NOW)
    erased = cascade(store, "alice", policy["targets"])
    assert accepted["status"] == "accepted"
    assert marker["state"] == "tombstoned"
    assert erased["complete"] is True
    assert verify_gone(store, "alice") == []


def test_tombstone_blocks_rewrite(store, policy):
    first = tombstone(store, "alice", NOW)
    second = tombstone(store, "alice", NOW + 2 * DAY)
    assert first["at"] == NOW
    assert second["at"] == NOW
    assert store["__tombstones__"]["alice"]["state"] == "tombstoned"
    with pytest.raises(PermissionError):
        accept_request(store, "alice", "write", NOW + 2 * DAY, policy)


def test_defect_02_tombstone_is_not_overwritten_by_write(store, policy):
    tombstone(store, "alice", NOW)
    with pytest.raises(PermissionError):
        accept_request(store, "alice", "write", NOW + 1, policy)
    assert store["__tombstones__"]["alice"]["at"] == NOW


def test_defect_03_cascade_removes_attached_stores(store, policy):
    result = cascade(store, "alice", policy["targets"])
    assert result["complete"] is True
    assert all("alice" not in store[name] for name in policy["targets"])


def test_attached_store_is_cleaned(store, policy):
    cascade(store, "alice", ["primary", "cache", "search"])
    assert "alice" not in store["cache"]
    assert "alice" not in store["search"]
    assert verify_gone(store, "alice") == []


def test_defect_04_cascade_requires_target_confirmation(store, policy):
    result = cascade(store, "alice", ["primary", "missing_archive"])
    assert result["targets"]["missing_archive"]["confirmed"] is False
    assert result["complete"] is False


def test_defect_05_verify_gone_checks_cache_and_search(store):
    store["cache"]["alice"] = {"last_seen": NOW}
    store["search"]["alice"] = {"indexed": True}
    assert set(verify_gone(store, "alice")) == {"cache", "search"}


def test_residual_check_finds_missed_store(store):
    del store["primary"]["alice"]
    store["cache"]["alice"] = {"last_seen": NOW}
    assert verify_gone(store, "alice") == ["cache"]


def test_defect_06_backup_policy_respects_retention(policy):
    young = {"id": "backup-young", "created_at": NOW, "now": NOW + 10 * DAY}
    due = {"id": "backup-due", "created_at": NOW, "now": NOW + 90 * DAY}
    assert backup_policy(young, policy) is False
    assert backup_policy(due, policy) is True


def test_defect_07_report_includes_elapsed_time(store, policy):
    accepted = accept_request(store, "alice", "erasure", NOW, policy)
    tombstone(store, "alice", NOW)
    cascade(store, "alice", policy["targets"])
    result = report(store, "alice", NOW + 120)
    assert result["deadline"] == accepted["deadline"]
    assert result["elapsed_seconds"] == 120
    assert result["within_deadline"] is True


def test_defect_08_report_marks_partial_success(store, policy):
    accept_request(store, "alice", "erasure", NOW, policy)
    tombstone(store, "alice", NOW)
    cascade(store, "alice", ["primary", "missing_archive"])
    result = report(store, "alice", NOW + 120)
    assert result["status"] == "partial"
    assert result["completed_targets"] == ["primary"]
    assert result["failed_targets"] == ["missing_archive"]


def test_defect_09_validate_policy_requires_residual_check(policy):
    policy["residual_check"] = False
    assert validate_policy(policy) == ["residual_check"]


def test_defect_10_batch_keeps_tombstones_per_request(store_factory, policy):
    requests = [
        {"user": "alice", "kind": "erasure", "store": store_factory("alice")},
        {"user": "bob", "kind": "erasure", "store": store_factory("bob")},
    ]
    result = dsr_batch(requests, policy, NOW)
    assert result["complete"] is True
    assert [item["status"] for item in result["results"]] == ["complete", "complete"]
    assert verify_gone(requests[1]["store"], "bob") == []


def test_two_batches_match_individual_runs(store_factory, policy):
    requests = [
        {"user": "alice", "kind": "erasure", "store": store_factory("alice")},
        {"user": "bob", "kind": "erasure", "store": store_factory("bob")},
    ]
    batch = dsr_batch(requests, policy, NOW)

    individual = []
    for user in ("alice", "bob"):
        single_store = store_factory(user)
        accept_request(single_store, user, "erasure", NOW, policy)
        tombstone(single_store, user, NOW)
        cascade(single_store, user, policy["targets"])
        individual.append((user, report(single_store, user, NOW)["status"]))

    observed = [(item["user"], item["status"]) for item in batch["results"]]
    assert observed == individual