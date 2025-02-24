async function callProtectedAPI() {
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
        console.error("No access token found, please log in first.");
        return;
    }

    const response = await fetch("http://127.0.0.1:8000/auth/protected", {
        method: "GET",
        headers: {
            "Authorization": "Bearer " + accessToken
        }
    });

    const data = await response.json();
    console.log("API Response:", data);
}

callProtectedAPI();
