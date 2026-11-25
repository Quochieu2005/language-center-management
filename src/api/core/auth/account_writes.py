"""Single write path for account identity fields: the authority row plus its outbox."""

from __future__ import annotations

# Internal callers only; values are always parameters, column names come from this allowlist.
_WRITABLE_COLUMNS = frozenset({"slug", "ten_dang_nhap", "email", "google_subject", "facebook_subject"})


class AccountVersionConflict(Exception):
    """The authority row changed after it was read; the caller must re-read and retry."""


def update_authority_account(cursor, account_id: str, expected_version: int, changes: dict) -> int:
    """Update the authority ``TaiKhoan`` row and bump ``phien_ban``.

    Replicas are never written here: ``TR_TaiKhoan_queue_replication`` enqueues every
    active site and ``sync_accounts`` overwrites older replicas. A bumped version is
    what lets the worker tell "stale replica" apart from a real conflict. Sessions of
    the same account are moved to the new version because these edits do not revoke
    access (password/status changes keep their own revoking paths).
    """
    if not changes or not set(changes) <= _WRITABLE_COLUMNS:
        raise ValueError("Cột tài khoản không được phép cập nhật qua đường này.")
    columns = sorted(changes)
    cursor.execute(
        "UPDATE dbo.TaiKhoan SET "
        + ", ".join(f"{column} = %s" for column in columns)
        + ", phien_ban = phien_ban + 1, cap_nhat_luc = SYSUTCDATETIME() "
        "WHERE ma_tai_khoan = %s AND phien_ban = %s",
        [*(changes[column] for column in columns), account_id, expected_version],
    )
    if cursor.rowcount != 1:
        raise AccountVersionConflict
    new_version = int(expected_version) + 1
    cursor.execute(
        "UPDATE dbo.PhienDangNhap SET phien_ban_tai_khoan = %s "
        "WHERE ma_tai_khoan = %s AND phien_ban_tai_khoan = %s AND thu_hoi_luc_utc IS NULL",
        [new_version, account_id, expected_version],
    )
    return new_version
