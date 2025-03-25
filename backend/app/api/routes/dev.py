from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.tests.utils.setup_test_data import setup_test_data

router = APIRouter(prefix="/dev", tags=["Development Utilities"])


@router.post("/seed-test-data")
def seed_test_data(db: Session = Depends(get_db)):
    """
    Populates the database with test records required for message-related tests.
    """
    setup_test_data(db)
    return {"status": "ok", "message": "Test data seeded"}
