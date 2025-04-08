# tests/api/v1/test_contacts.py

import pytest
import pytest_asyncio
from uuid import uuid4, UUID
from httpx import AsyncClient
from fastapi import status  # Use status codes from fastapi or http.HTTPStatus
from loguru import logger

# Import schemas for request/response validation if needed (often implicitly tested)
from app.api.schemas.contact import (
    ContactRead,
    PaginatedContactRead,
    ContactCreate,
    ContactUpdate,
)

# Import models for potential direct DB checks or fixture type hints
from app.models.contact import Contact
from app.models.account import Account

# Use phonenumbers for creating valid/invalid numbers for tests
import phonenumbers
from app.services.helper.contact import (
    normalize_phone_number,
)  # Import your actual normalizer

# --- Test Data ---

VALID_PHONE_INTERNATIONAL = "+44 20 7123 4567"  # UK example
NORMALIZED_PHONE_INTERNATIONAL = "442071234567"

VALID_PHONE_BR = "11 98765 4321"  # Brazil example
NORMALIZED_PHONE_BR = "5511987654321"  # Assuming 'BR' is default or passed

INVALID_PHONE = "abcdefg"

API_V1_PREFIX = "/api/v1"

# --- Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_contact_success(client: AsyncClient, test_account: Account):
    """
    Test successfully creating a new contact.
    """
    payload = {
        "name": "John Doe",
        "phone_number": VALID_PHONE_BR,
        "email": "john.doe@example.com",
        "additional_attributes": {"company": "Test Inc."},
    }
    response = await client.post(f"{API_V1_PREFIX}/contacts", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["email"] == payload["email"]
    # Check if phone number and identifier are normalized correctly
    assert data["phone_number"] == NORMALIZED_PHONE_BR
    assert data["identifier"] == NORMALIZED_PHONE_BR
    assert data["account_id"] == str(test_account.id)
    assert data["additional_attributes"] == payload["additional_attributes"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_contact_conflict(client: AsyncClient, test_contact: Contact):
    """
    Test creating a contact with a phone number that already exists for the account.
    """
    payload = {
        "name": "Jane Doe",
        "phone_number": test_contact.phone_number,  # Use existing contact's phone
    }
    response = await client.post(f"{API_V1_PREFIX}/contacts", json=payload)

    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert "detail" in data
    # Check if the detail message indicates conflict
    assert "already exists" in data["detail"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_contact_invalid_phone(client: AsyncClient):
    """
    Test creating a contact with an invalid/unparseable phone number.
    """
    payload = {"name": "Invalid Phone User", "phone_number": INVALID_PHONE}
    response = await client.post(f"{API_V1_PREFIX}/contacts", json=payload)

    # Expecting 400 based on repository logic raising HTTPException for invalid numbers
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_contact_missing_phone(client: AsyncClient):
    """
    Test creating a contact missing the required phone_number field (schema validation).
    """
    payload = {
        "name": "No Phone User",
        # "phone_number": "..." missing
    }
    response = await client.post(f"{API_V1_PREFIX}/contacts", json=payload)

    # FastAPI/Pydantic should return 422 for validation errors
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# # --- List Contacts Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_contacts_empty(client: AsyncClient):
    """
    Test listing contacts when none exist for the account.
    """
    response = await client.get(f"{API_V1_PREFIX}/contacts")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_contacts_with_data(client: AsyncClient, test_contact: Contact):
    """
    Test listing contacts when one exists.
    """
    response = await client.get(f"{API_V1_PREFIX}/contacts")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    contact_data = data["items"][0]
    assert contact_data["id"] == str(test_contact.id)
    assert contact_data["name"] == test_contact.name
    assert (
        contact_data["phone_number"] == test_contact.phone_number
    )  # Should be normalized


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_contacts_pagination(
    client: AsyncClient, test_account: Account, db_session
):
    """
    Test pagination (offset and limit) for listing contacts.
    """
    # Create 3 contacts for pagination test
    contacts_to_create = []
    for i in range(3):
        # Ensure unique phone numbers for creation
        raw_phone = f"+1 202 555 017{i}"
        normalized = normalize_phone_number(raw_phone)
        print(raw_phone, normalized)
        contact = Contact(
            id=uuid4(),
            account_id=test_account.id,
            name=f"Paginated Contact {i}",
            phone_number=normalized,  # Store normalized
            identifier=normalized,
        )
        contacts_to_create.append(contact)

    db_session.add_all(contacts_to_create)
    await db_session.commit()
    # Sort by creation time descending (as in the endpoint) for predictable order
    # Note: If creation times are too close, order might be ambiguous. Consider sorting by name or ID.
    # Assuming created_at is distinct enough or default order is stable for test.
    # Let's sort by name for predictability in test
    contacts_to_create.sort(key=lambda c: c.created_at, reverse=True)

    # Test limit=1
    response_limit1 = await client.get(f"{API_V1_PREFIX}/contacts?limit=1")
    assert response_limit1.status_code == status.HTTP_200_OK
    data_limit1 = response_limit1.json()
    assert data_limit1["total"] == 3
    assert len(data_limit1["items"]) == 1
    assert data_limit1["items"][0]["id"] == str(contacts_to_create[0].id)  # Most recent

    # Test limit=1, offset=1
    response_offset1 = await client.get(f"{API_V1_PREFIX}/contacts?limit=1&offset=1")
    assert response_offset1.status_code == status.HTTP_200_OK
    data_offset1 = response_offset1.json()
    assert data_offset1["total"] == 3
    assert len(data_offset1["items"]) == 1
    assert data_offset1["items"][0]["id"] == str(
        contacts_to_create[1].id
    )  # Second most recent

    # Test limit=5 (more than total)
    response_limit5 = await client.get(f"{API_V1_PREFIX}/contacts?limit=5")
    assert response_limit5.status_code == status.HTTP_200_OK
    data_limit5 = response_limit5.json()
    assert data_limit5["total"] == 3
    assert len(data_limit5["items"]) == 3


# --- Get Single Contact Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_contact_success(client: AsyncClient, test_contact: Contact):
    """
    Test getting a specific contact by its ID successfully.
    """
    response = await client.get(f"{API_V1_PREFIX}/contacts/{test_contact.id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(test_contact.id)
    assert data["name"] == test_contact.name
    assert data["phone_number"] == test_contact.phone_number
    assert data["identifier"] == test_contact.identifier
    assert data["account_id"] == str(test_contact.account_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_contact_not_found(client: AsyncClient):
    """
    Test getting a contact with a non-existent ID.
    """
    non_existent_id = uuid4()
    response = await client.get(f"{API_V1_PREFIX}/contacts/{non_existent_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# # --- Update Contact Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_contact_success_name(client: AsyncClient, test_contact: Contact):
    """
    Test successfully updating a contact's name.
    """
    update_payload = {"name": "Updated Name"}
    response = await client.put(
        f"{API_V1_PREFIX}/contacts/{test_contact.id}", json=update_payload
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(test_contact.id)
    assert data["name"] == update_payload["name"]
    assert (
        data["phone_number"] == test_contact.phone_number
    )  # Phone should be unchanged


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_contact_success_phone(client: AsyncClient, test_contact: Contact):
    """
    Test successfully updating a contact's phone number.
    """
    new_phone_raw = VALID_PHONE_INTERNATIONAL
    new_phone_normalized = NORMALIZED_PHONE_INTERNATIONAL
    update_payload = {"phone_number": new_phone_raw}

    response = await client.put(
        f"{API_V1_PREFIX}/contacts/{test_contact.id}", json=update_payload
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(test_contact.id)
    assert data["phone_number"] == new_phone_normalized  # Check normalization
    assert data["identifier"] == new_phone_normalized  # Check identifier update


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_contact_not_found(client: AsyncClient):
    """
    Test updating a contact that does not exist.
    """
    non_existent_id = uuid4()
    update_payload = {"name": "Ghost Update"}
    response = await client.put(
        f"{API_V1_PREFIX}/contacts/{non_existent_id}", json=update_payload
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_contact_phone_conflict(
    client: AsyncClient, test_account: Account, db_session
):
    """
    Test updating a contact's phone number to one that already exists for another contact.
    """
    # Create two contacts
    contact1_phone_raw = "+1 202 555 0172"
    contact1_norm = normalize_phone_number(contact1_phone_raw)
    contact1 = Contact(
        id=uuid4(),
        account_id=test_account.id,
        name="Contact One",
        phone_number=contact1_norm,
        identifier=contact1_norm,
    )

    contact2_phone_raw = "+1 202 555 0174"
    contact2_norm = normalize_phone_number(contact2_phone_raw)
    contact2 = Contact(
        id=uuid4(),
        account_id=test_account.id,
        name="Contact Two",
        phone_number=contact2_norm,
        identifier=contact2_norm,
    )

    db_session.add_all([contact1, contact2])
    await db_session.commit()
    await db_session.refresh(contact1)
    await db_session.refresh(contact2)

    # Try to update contact1's phone to contact2's phone
    update_payload = {
        "phone_number": contact2_phone_raw
    }  # Use raw number for update request
    response = await client.put(
        f"{API_V1_PREFIX}/contacts/{contact1.id}", json=update_payload
    )

    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_contact_invalid_phone(client: AsyncClient, test_contact: Contact):
    """
    Test updating a contact with an invalid/unparseable phone number.
    """
    update_payload = {"phone_number": INVALID_PHONE}
    response = await client.put(
        f"{API_V1_PREFIX}/contacts/{test_contact.id}", json=update_payload
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_contact_validation_error(
    client: AsyncClient, test_contact: Contact
):
    """
    Test updating a contact with invalid data type (schema validation).
    """
    update_payload = {"name": 12345}  # Name should be string
    response = await client.put(
        f"{API_V1_PREFIX}/contacts/{test_contact.id}", json=update_payload
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# # --- Delete Contact Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_contact_success(
    client: AsyncClient, test_contact: Contact, db_session
):
    """
    Test successfully deleting a contact.
    """
    contact_id_to_delete = test_contact.id
    response = await client.delete(f"{API_V1_PREFIX}/contacts/{contact_id_to_delete}")

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's actually deleted from DB
    # Need to use the db_session fixture directly for verification
    deleted_contact = await db_session.get(Contact, contact_id_to_delete)
    assert deleted_contact is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_contact_not_found(client: AsyncClient):
    """
    Test deleting a contact that does not exist.
    """
    non_existent_id = uuid4()
    response = await client.delete(f"{API_V1_PREFIX}/contacts/{non_existent_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# # --- Authentication Test ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contact_endpoints_unauthenticated(unauthenticated_client: AsyncClient):
    """
    Test that contact endpoints require authentication.
    """
    # Test one endpoint, e.g., GET list
    response = await unauthenticated_client.get(f"{API_V1_PREFIX}/contacts")
    # Expecting 401 or 403 depending on auth middleware setup
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]
