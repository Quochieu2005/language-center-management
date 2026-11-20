"""Publisher-only entry points for shared MonHoc creation and deletion."""


def create_shared_subject(*, subject: dict, idempotency_key: str, actor_id: str) -> dict:
    from core.catalog.publisher_subjects import write_subject

    return write_subject(action="tao", slug=subject["slug"], payload=subject,
                         idempotency_key=idempotency_key, actor_id=actor_id)


def delete_shared_subject(*, slug: str, idempotency_key: str, actor_id: str) -> dict:
    from core.catalog.publisher_subjects import write_subject

    return write_subject(action="xoa", slug=slug, payload={},
                         idempotency_key=idempotency_key, actor_id=actor_id)
