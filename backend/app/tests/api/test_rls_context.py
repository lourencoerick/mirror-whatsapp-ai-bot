import pytest
from sqlalchemy import text
from app.database import SessionLocal
from app.middleware.account_context import set_account_id


@pytest.mark.integration
def test_set_local_applies_account_id():
    set_account_id(123)

    with SessionLocal() as db:
        with db.begin():
            result = db.execute(text("SHOW my.app.account_id")).scalar()
            assert result == "123"
