const AUTH0_DOMAIN = "dev-dhatrtlc6w4vn5rv.us.auth0.com";
const CLIENT_ID = "zqSnOLtR342KZKIICSZ0zRJKK5UkPCIc";
const REDIRECT_URI = "http://localhost:3001/callback";


async function exchangeCodeForToken() {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const code_verifier = localStorage.getItem("code_verifier");
    // const code_verifier = sessionStorage.getItem("code_verifier"); // ✅ Retrieve from `sessionStorage`


    if (!code) {
        console.error("No authorization code found in URL");
        return;
    }

    console.log("🔹 Authorization Code:", code);
    console.log("🔹 Code Verifier:", code_verifier);

    const tokenEndpoint = `https://${AUTH0_DOMAIN}/oauth/token`;

    const requestBody = new URLSearchParams({
        client_id: CLIENT_ID,
        grant_type: "authorization_code",
        code: code,
        redirect_uri: REDIRECT_URI,
        code_verifier: code_verifier
    });

    console.log("🔹 Token Request Payload:", requestBody.toString());

    try {
        const response = await fetch(tokenEndpoint, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: requestBody
        });

        const data = await response.json();
        console.log("🔹 Token Response:", data);

        if (data.access_token) {
            localStorage.setItem("access_token", data.access_token);
            localStorage.setItem("refresh_token", data.refresh_token);
            console.log("✅ Access Token Stored!");
            window.location.href = "/profile.html"; // Redirect if needed
        } else {
            console.error("❌ Token Exchange Failed:", data);
        }
    } catch (error) {
        console.error("❌ Token Exchange Error:", error);
    }
}

exchangeCodeForToken();
