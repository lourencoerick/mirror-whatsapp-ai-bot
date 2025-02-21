from fastapi import FastAPI

# Create an instance of the FastAPI class
app = FastAPI()


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify if the application is running.

    Returns:
        dict: A dictionary containing the status of the application.
    """
    return {"status": "healthy"}
