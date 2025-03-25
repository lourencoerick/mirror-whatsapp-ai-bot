import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import pytest


# Integration test: This test connects to a real database.
@pytest.mark.integration
def test_connection():
    # Load environment variables from the .env file
    load_dotenv()

    # Retrieve database configuration from environment variables
    dbname = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")

    try:
        # Attempt to connect to the PostgreSQL database using psycopg2
        connection = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host, port=port
        )
        cursor = connection.cursor()
        # Execute a simple query to verify the connection
        cursor.execute("SELECT 1")
        print("Database connection is working!")
    except Exception as e:
        print(f"Error connecting to database: {e}")
    finally:
        # Ensure that the connection is closed properly
        if connection:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    test_connection()
