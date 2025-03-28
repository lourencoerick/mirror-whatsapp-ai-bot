from uuid import uuid4
import pytest
from sqlalchemy import text
from app.database import SessionLocal
from app.middleware.account_context import set_account_id


@pytest.mark.integration
def test_set_local_applies_account_id():
    account_id = uuid4()
    set_account_id(account_id)

    with SessionLocal() as db:
        with db.begin():
            result = db.execute(text("SHOW my.app.account_id")).scalar()
            assert result == str(account_id)
