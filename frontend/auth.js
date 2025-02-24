const AUTH0_DOMAIN = "dev-dhatrtlc6w4vn5rv.us.auth0.com";
const CLIENT_ID = "zqSnOLtR342KZKIICSZ0zRJKK5UkPCIc";
const REDIRECT_URI = "http://localhost:3001/callback";
const API_AUDIENCE = "lambda-labs";

// async function generatePKCE() {
//     let code_verifier = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
//     let encoder = new TextEncoder();
//     let data = encoder.encode(code_verifier);
//     let digest = await crypto.subtle.digest('SHA-256', data);
//     let code_challenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
//                           .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

//     console.log("🔹 Generated Code Verifier:", code_verifier);
//     console.log("🔹 Generated Code Challenge:", code_challenge);                          
//     return { code_verifier, code_challenge };
// }


async function generatePKCE() {
    let code_verifier = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))))
                          .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); // ✅ Make it URL-safe
    
    let encoder = new TextEncoder();
    let data = encoder.encode(code_verifier);
    let digest = await crypto.subtle.digest('SHA-256', data);
    let code_challenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
                          .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); // ✅ Also URL-safe

    console.log("🔹 Generated Code Verifier (URL Safe):", code_verifier);
    console.log("🔹 Generated Code Challenge (SHA-256):", code_challenge);

    return { code_verifier, code_challenge };
}


async function login() {
    const { code_verifier, code_challenge } = await generatePKCE();
    // Critical line: make sure this runs before redirection
    console.log("✅ Code Verifier Stored:", code_verifier);
    localStorage.setItem("code_verifier", code_verifier);  
    sessionStorage.setItem("code_verifier", code_verifier);
    console.log("✅ Code Verifier Stored:", code_verifier);


    window.location.href = `https://${AUTH0_DOMAIN}/authorize?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=openid profile email&audience=${API_AUDIENCE}&code_challenge=${code_challenge}&code_challenge_method=S256`;
}



// Add event listener properly
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("login-btn").onclick = login;
});

// https://dev-dhatrtlc6w4vn5rv.us.auth0.com/authorize%20%20%20%20%20%20?response_type=code%20%20%20%20%20%20&client_id=zqSnOLtR342KZKIICSZ0zRJKK5UkPCIc%20%20%20%20%20%20&redirect_uri=http://localhost:8000/auth/callback%20%20%20%20%20%20&scope=openid%20profile%20email%20%20%20%20%20%20&audience=lambda-labs%20%20%20%20%20%20&code_challenge=vC9YjHQeHFmIPERBEE4UrrarvOzuAyMjYS_HEL2aYUI%20%20%20%20%20%20&code_challenge_method=S256
