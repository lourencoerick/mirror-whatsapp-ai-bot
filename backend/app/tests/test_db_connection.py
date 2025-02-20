import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


def test_connection():
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
        cursor.execute("SELECT 1")
        print("Database connection is working!")
    except Exception as e:
        print(f"Error connecting to database: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    test_connection()
