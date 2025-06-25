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
 * Represents the user-provided parameters for a Google Analytics event.
 * These are the custom dimensions and metrics for an event.
 */
type GtagEventParams = {
  [key: string]: string | number | undefined;
};

/**
 * Defines the complete payload structure for a gtag event call.
 * This type is compatible with all possible properties, including the
 * specific 'event_callback' function and 'send_to' string, as well as
 * the dynamic user-provided parameters.
 */
interface GtagPayload {
  event_callback?: () => void;
  send_to?: string | string[];
  // This index signature allows for any other string keys with values
  // that are common in GA event tracking.
  [key: string]: string | number | undefined | (() => void) | string[];
}

/**
 * Sends a generic event to all configured analytics platforms (GA, Google Ads).
 * This is our central tracking function.
 *
 * @param {string} eventName - The name of the event (e.g., 'conversion_signup').
 * @param {GtagEventParams} params - An object of key-value pairs for event context.
 * @param {Function} [callback] - An optional callback to run after the event is sent.
 * @param {boolean} [isAdsConversion=false] - Set to true to also send this event as a Google Ads conversion.
 */
export const trackEvent = (
  eventName: string,
  params: GtagEventParams,
  callback?: () => void,
  isAdsConversion: boolean = false
): void => {

  const GA_ID = process.env.NEXT_PUBLIC_GA_ID || "G-8N395BDYFG";
  const ADS_CONVERSION_ID = process.env.NEXT_PUBLIC_ADS_CONVERSION_ID || "AW-16914772618/VzaiCJzk26gaEIrly4E_";

  if (typeof window === 'undefined' || typeof window.gtag !== 'function' || !GA_ID) {
    console.warn('GA tracking is disabled or not configured. Running callback directly.');
    if (callback) {
      callback();
    }
    return;
  }

  // This object is now correctly typed as GtagPayload.
  const eventPayload: GtagPayload = {
    ...params,
    event_callback: callback,
  };

  if (isAdsConversion && ADS_CONVERSION_ID) {
    eventPayload.send_to = [GA_ID, ADS_CONVERSION_ID];;
  }

  window.gtag('event', eventName, eventPayload);
};