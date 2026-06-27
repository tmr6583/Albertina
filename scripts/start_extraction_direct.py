from __future__ import annotations

from sqlalchemy import text

from backend.olist_extraction.service import extraction_service


def main() -> int:
    service = extraction_service
    repository = service._get_repository()
    with repository.engine.connect() as connection:
        admin_id = connection.execute(
            text("SELECT id FROM public.users WHERE lower(email) = lower(:email) LIMIT 1"),
            {"email": "admin@empresa.com"},
        ).scalar_one()

    result = service.start_full_sync(user_id=str(admin_id), actor_email="admin@empresa.com")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
