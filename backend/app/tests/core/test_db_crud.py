import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


def create_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_table (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        )
    """
    )


def insert_data(cursor, name):
    cursor.execute("INSERT INTO test_table (name) VALUES (%s) RETURNING id", (name,))
    return cursor.fetchone()[0]


def read_data(cursor, id):
    cursor.execute("SELECT * FROM test_table WHERE id = %s", (id,))
    return cursor.fetchone()


def update_data(cursor, id, new_name):
    cursor.execute("UPDATE test_table SET name = %s WHERE id = %s", (new_name, id))


def delete_data(cursor, id):
    cursor.execute("DELETE FROM test_table WHERE id = %s", (id,))


def test_crud_operations():
    load_dotenv()

    dbname = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")

    try:
        connection = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host, port=port
        )
        cursor = connection.cursor()

        # Create table
        create_table(cursor)
        connection.commit()
        print("Table created successfully.")

        # Insert data
        id = insert_data(cursor, "Test Name")
        connection.commit()
        print(f"Data inserted successfully with id: {id}")

        # Read data
        data = read_data(cursor, id)
        print(f"Data read successfully: {data}")

        # Update data
        update_data(cursor, id, "New Test Name")
        connection.commit()
        print("Data updated successfully.")

        # Read updated data
        data = read_data(cursor, id)
        print(f"Updated data read successfully: {data}")

        # Delete data
        delete_data(cursor, id)
        connection.commit()
        print("Data deleted successfully.")

        # Read deleted data
        data = read_data(cursor, id)
        print(f"Data after deletion: {data}")

    except Exception as e:
        print(f"Error during CRUD operations: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    test_crud_operations()
