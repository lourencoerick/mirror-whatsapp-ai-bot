import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import pytest


def create_table(cursor):
    # Create a table named test_table if it does not already exist.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_table (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        )
        """
    )


def insert_data(cursor, name):
    # Insert a record into test_table and return the generated id.
    cursor.execute("INSERT INTO test_table (name) VALUES (%s) RETURNING id", (name,))
    return cursor.fetchone()[0]


def read_data(cursor, id):
    # Read a record from test_table based on the provided id.
    cursor.execute("SELECT * FROM test_table WHERE id = %s", (id,))
    return cursor.fetchone()


def update_data(cursor, id, new_name):
    # Update the name field of a record in test_table based on the id.
    cursor.execute("UPDATE test_table SET name = %s WHERE id = %s", (new_name, id))


def delete_data(cursor, id):
    # Delete a record from test_table based on the id.
    cursor.execute("DELETE FROM test_table WHERE id = %s", (id,))


# Integration test for CRUD operations on the PostgreSQL database.
# This test interacts with a real database and performs Create, Read, Update, and Delete operations.
@pytest.mark.integration
def test_crud_operations():
    # Load environment variables from the .env file
    load_dotenv()

    # Retrieve database connection parameters from environment variables
    dbname = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")

    connection = None

    try:
        # Establish connection to the PostgreSQL database
        connection = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host, port=port
        )
        cursor = connection.cursor()

        # Create the table
        create_table(cursor)
        connection.commit()
        print("Table created successfully.")

        # Insert data and commit the transaction
        inserted_id = insert_data(cursor, "Test Name")
        connection.commit()
        print(f"Data inserted successfully with id: {inserted_id}")

        # Read the inserted data
        data = read_data(cursor, inserted_id)
        print(f"Data read successfully: {data}")

        # Update the data and commit the change
        update_data(cursor, inserted_id, "New Test Name")
        connection.commit()
        print("Data updated successfully.")

        # Read the updated data
        data = read_data(cursor, inserted_id)
        print(f"Updated data read successfully: {data}")

        # Delete the data and commit the deletion
        delete_data(cursor, inserted_id)
        connection.commit()
        print("Data deleted successfully.")

        # Try to read the deleted data
        data = read_data(cursor, inserted_id)
        print(f"Data after deletion: {data}")

    except Exception as e:
        print(f"Error during CRUD operations: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    test_crud_operations()
