/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * @file Analytics services for tracking conversions and user data.
 */

/**
 * Hashes a string value using the SHA-256 algorithm.
 * Used for sending user data to Google Analytics in a privacy-compliant way.
 * @param {string} value The string to hash.
 * @returns {Promise<string>} The hex representation of the hash.
 */
async function hashSHA256(value: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(value.trim().toLowerCase());
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Sends hashed user data to Google Analytics.
 * @param {object} userData The user data.
 * @param {string} userData.name The user's name.
 * @param {string} userData.email The user's email.
 */
export async function setGoogleAnalyticsUserData(userData: { name: string; email: string }): Promise<void> {
  if (typeof window === "undefined" || typeof (window as any).gtag !== "function") {
    return;
  }
  const hashedEmail = await hashSHA256(userData.email);
  const hashedName = await hashSHA256(userData.name);

  (window as any).gtag('set', 'user_data', {
    email: hashedEmail,
    first_name: hashedName,
  });
}

/**
 * Reports a conversion event to Google Ads.
 * @param {Function} [callback] An optional callback function to run after the event is sent.
 */
export function trackGoogleAdsConversion(callback?: () => void): void {
  if (typeof window === "undefined" || typeof (window as any).gtag !== 'function') {
    console.warn("gtag function not found. Running callback directly.");
    if (callback) callback();
    return;
  }

  (window as any).gtag("event", "click_beta_signup", {
    send_to: ["AW-16914772618/VzaiCJzk26gaEIrly4E_", "G-8N395BDYFG/click_beta_signup"],
    
    event_callback: callback,
  });
}