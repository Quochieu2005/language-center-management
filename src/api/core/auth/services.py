"""Compatibility exports for authentication service callers.

Implementation is separated by responsibility; keep imports from this module
working while callers migrate to narrower service modules.
"""

from core.auth.service_common import (
    AuthInfrastructureUnavailable,
    LoginRateLimitExceeded,
    PasswordResetRateLimitExceeded,
    AdminSmallAccountConflict,
    AdminSmallSiteUnavailable,
    AdminSmallProfileNotFound,
    AdminSmallTargetNotFound,
    AdminSmallDeleteConflict,
    AuthenticatedUser,
    AuthenticatedSession,
    AdminSmallProvisioningResult,
    AdminSmallDeactivationResult,
    auth_session_alias,
    _digest,
    session_token_digest,
    _read_catalog,
    active_site_codes,
    _replicated_account,
    _replicated_account_by_id,
    _resolve_principal,
    _acquire_ip_lock,
    _rate_limit_wait,
    _record_attempt,
    _acquire_named_lock,
    _next_sequence_number,
    auth_session_site_code,
)

from core.auth.password_reset import (
    _record_password_reset_event,
    _password_reset_request_is_limited,
    _password_reset_verify_retry_after,
    _eligible_admin_from_email,
    _invalidate_reset_token,
    request_admin_password_reset,
    _apply_password_reset_transaction,
    _resume_pending_password_resets,
    reset_admin_password,
)

from core.auth.admin_small_profiles import (
    _admin_small_profile_cursor,
    get_admin_small_self_profile,
    update_admin_small_self_profile,
)

from core.auth.admin_small_lifecycle import (
    delete_admin_small,
    create_admin_small,
)

from core.auth.session_services import (
    change_authenticated_password,
    login_user,
    load_user_session,
    extend_user_session,
    revoke_user_session,
)
