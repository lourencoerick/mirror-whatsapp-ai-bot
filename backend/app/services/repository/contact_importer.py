import csv
import io

# ... inside process_contact_csv


async def process_contact_csv(
    db: AsyncSession, account_id: UUID, file: UploadFile
) -> ContactImportSummary:

    errors_list: List[ContactImportError] = []
    successful_count = 0
    processed_count = 0
    reader = None  # Initialize reader

    try:
        content_str = content_bytes.decode("utf-8")
        csvfile = io.StringIO(content_str)
        reader = csv.DictReader(csvfile)
        headers = reader.fieldnames
        # TODO: Validate headers contain required fields ('phone_number', etc.)
        if not headers or "phone_number" not in headers:
            raise ValueError("CSV must contain at least a 'phone_number' column.")

    except (UnicodeDecodeError, ValueError, csv.Error) as e:
        # Handle file reading/parsing errors
        raise HTTPException(
            status_code=400, detail=f"Error reading or parsing CSV file: {e}"
        )

    # Ensure reader is not None before proceeding
    if reader is None:
        raise HTTPException(
            status_code=500, detail="CSV reader could not be initialized."
        )

    for i, row in enumerate(reader):
        row_number = i + 2  # +1 for 0-index, +1 for header row
        processed_count += 1
        try:
            # Validate row data using Pydantic schema
            # Map CSV columns to ContactCreate fields (handle case sensitivity/spaces in headers)
            # Example basic mapping (adjust based on expected CSV columns):
            contact_data_dict = {
                "name": row.get("name") or row.get("Name"),  # Handle different cases
                "phone_number": row.get("phone_number") or row.get("Phone Number"),
                "email": row.get("email") or row.get("Email"),
                # Add other fields like additional_attributes if needed
            }
            # Remove None values if schema fields are optional
            contact_data_dict = {
                k: v for k, v in contact_data_dict.items() if v is not None and v != ""
            }

            # Check if essential phone number is present after mapping
            if not contact_data_dict.get("phone_number"):
                raise ValueError("Missing 'phone_number' in row.")

            # Use ContactCreate for validation
            contact_create_schema = ContactCreate(**contact_data_dict)

            # Attempt to create contact using repository function
            await contact_repo.create_contact(
                db=db, contact_data=contact_create_schema, account_id=account_id
            )
            successful_count += 1

        except ValidationError as e:  # Pydantic validation error
            errors_list.append(
                ContactImportError(
                    row_number=row_number,
                    reason=f"Validation Error: {e.errors()}",  # Get detailed errors
                    data=row,
                )
            )
        except HTTPException as e:  # Errors from create_contact (400, 409)
            errors_list.append(
                ContactImportError(
                    row_number=row_number,
                    reason=f"API Error ({e.status_code}): {e.detail}",
                    data=row,
                )
            )
        except Exception as e:  # Catch other unexpected errors per row
            errors_list.append(
                ContactImportError(
                    row_number=row_number,
                    reason=f"Unexpected Error: {str(e)}",
                    data=row,
                )
            )

    # Return summary
    return ContactImportSummary(
        total_rows_processed=processed_count,
        successful_imports=successful_count,
        failed_imports=len(errors_list),
        errors=errors_list,
    )
