const AUTH0_DOMAIN = "dev-dhatrtlc6w4vn5rv.us.auth0.com";

async function callUserInfoAPI() {
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
        console.error("No access token found, please log in first.");
        return;
    }

    try {
        const response = await fetch(`https://${AUTH0_DOMAIN}/userinfo`, {
            method: "GET",
            headers: {
                "Authorization": "Bearer " + accessToken
            }
        });

        if (response.ok) {
            const data = await response.json();
            console.log("User Info Response:", data);

            document.getElementById("username").textContent = data.name || "N/A";
            document.getElementById("email").textContent = data.email || "N/A";
            document.getElementById("profile-pic").src = data.picture || "";

        } else {
            console.error("User Info API call failed:", response.statusText);
            document.getElementById("api-response").textContent = "User Info API call failed: " + response.statusText;
        }
    } catch (error) {
        console.error("User Info API call error:", error);
        document.getElementById("api-response").textContent = "User Info API call error: " + error.message;
    }
}

async function callProtectedAPI() {
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
        console.error("No access token found, please log in first.");
        return;
    }

    try {
        const response = await fetch("http://127.0.0.1:8000/auth/protected", {
            method: "GET",
            headers: {
                "Authorization": "Bearer " + accessToken
            }
        });

        if (response.ok) {
            const data = await response.json();
            console.log("Protected API Response:", data);

            document.getElementById("api-response").textContent = JSON.stringify(data, null, 2);
        } else {
            console.error("Protected API call failed:", response.statusText);
            document.getElementById("api-response").textContent = "Protected API call failed: " + response.statusText;
        }
    } catch (error) {
        console.error("Protected API call error:", error);
        document.getElementById("api-response").textContent = "Protected API call error: " + error.message;
    }
}

function logout() {
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("refresh_token");
    window.location.href = "index.html";
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("logout-btn").onclick = logout;
    callUserInfoAPI();
    callProtectedAPI();
});