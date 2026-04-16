from app.db.seeds import seed_reference_data
from app.db.session import get_session_factory


def main() -> None:
    session_factory = get_session_factory()
    db = session_factory()

    try:
        summary = seed_reference_data(db)
        db.commit()
        print("Reference data seeded successfully.")
        print(summary)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()