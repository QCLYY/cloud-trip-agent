from pathlib import Path
import sys
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Base  # noqa: E402
from app.models.schemas import TripRequest  # noqa: E402
from app.services.storage_service import (  # noqa: E402
    compare_trip_versions,
    delete_itinerary_by_trip_id,
    get_itinerary_by_trip_id,
    get_trip_version,
    list_trip_versions,
    restore_trip_version,
    save_itinerary,
)
from app.services.trip_service import generate_trip_itinerary  # noqa: E402


@pytest.fixture()
def storage_session(tmp_path):
    db_path = tmp_path / "storage_test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def build_trip_request() -> TripRequest:
    return TripRequest(
        destination="大理",
        start_date="2026-04-10",
        end_date="2026-04-12",
        travelers=2,
        budget=3200,
        preferences=["自然风景", "拍照", "美食"],
        pace="轻松",
        dietary_preferences=["少辣"],
        hotel_level="舒适型",
        special_notes="不想太早起床，希望安排一个适合看日落的地点",
    )


def test_save_itinerary_returns_trip_id(storage_session) -> None:
    itinerary = generate_trip_itinerary(build_trip_request())
    itinerary.trip_id = f"{itinerary.trip_id}_{uuid.uuid4().hex[:8]}"

    saved_trip_id = save_itinerary(itinerary, session=storage_session)

    assert saved_trip_id == itinerary.trip_id


def test_get_itinerary_by_trip_id_returns_saved_result(storage_session) -> None:
    itinerary = generate_trip_itinerary(build_trip_request())
    itinerary.trip_id = f"{itinerary.trip_id}_{uuid.uuid4().hex[:8]}"

    save_itinerary(itinerary, session=storage_session)
    trip_detail = get_itinerary_by_trip_id(itinerary.trip_id, session=storage_session)

    assert trip_detail is not None
    assert trip_detail.trip_id == itinerary.trip_id
    assert trip_detail.itinerary.destination == "大理"
    assert len(trip_detail.itinerary.days) == 3


def test_get_itinerary_by_trip_id_returns_none_for_missing_trip(storage_session) -> None:
    trip_detail = get_itinerary_by_trip_id("trip_not_exists", session=storage_session)
    assert trip_detail is None


def test_save_itinerary_creates_versions(storage_session) -> None:
    itinerary = generate_trip_itinerary(build_trip_request())
    itinerary.trip_id = f"{itinerary.trip_id}_{uuid.uuid4().hex[:8]}"

    save_itinerary(itinerary, session=storage_session, change_type="first_save")
    edited = itinerary.model_copy(update={"summary": "changed summary"})
    save_itinerary(edited, session=storage_session, change_type="manual_save")

    versions = list_trip_versions(itinerary.trip_id, session=storage_session)

    assert versions.total == 2
    assert [item.version_number for item in versions.items] == [2, 1]
    assert versions.items[0].change_type == "manual_save"
    assert versions.items[1].change_type == "first_save"


def test_get_compare_and_restore_trip_versions(storage_session) -> None:
    itinerary = generate_trip_itinerary(build_trip_request())
    itinerary.trip_id = f"{itinerary.trip_id}_{uuid.uuid4().hex[:8]}"

    save_itinerary(itinerary, session=storage_session, change_type="first_save")
    edited = itinerary.model_copy(update={"summary": "changed summary"})
    save_itinerary(edited, session=storage_session, change_type="manual_save")

    version_one = get_trip_version(itinerary.trip_id, 1, session=storage_session)
    comparison = compare_trip_versions(
        itinerary.trip_id,
        from_version=1,
        to_version=2,
        session=storage_session,
    )
    restored = restore_trip_version(itinerary.trip_id, 1, session=storage_session)

    assert version_one is not None
    assert version_one.version_number == 1
    assert comparison is not None
    assert "summary changed" in comparison.differences
    assert restored is not None
    assert restored.restored_from_version == 1
    assert restored.new_version_number == 3
    assert restored.itinerary.summary == itinerary.summary


def test_delete_itinerary_removes_versions_from_public_access(storage_session) -> None:
    itinerary = generate_trip_itinerary(build_trip_request())
    itinerary.trip_id = f"{itinerary.trip_id}_{uuid.uuid4().hex[:8]}"

    save_itinerary(itinerary, session=storage_session, change_type="first_save")
    assert list_trip_versions(itinerary.trip_id, session=storage_session).total == 1

    deleted = delete_itinerary_by_trip_id(itinerary.trip_id, session=storage_session)

    assert deleted is True
    assert get_itinerary_by_trip_id(itinerary.trip_id, session=storage_session) is None
    assert list_trip_versions(itinerary.trip_id, session=storage_session).total == 0
    assert get_trip_version(itinerary.trip_id, 1, session=storage_session) is None
