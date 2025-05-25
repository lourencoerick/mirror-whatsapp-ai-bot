// src/lib/api/billing.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch"; // Adjust path if necessary
import { components } from "@/types/api"; // Your generated OpenAPI types

// Request and Response types for billing endpoints
type CreateCheckoutSessionRequest =
  components["schemas"]["CreateCheckoutSessionRequest"];
type CreateCheckoutSessionResponse =
  components["schemas"]["CreateCheckoutSessionResponse"];
type CustomerPortalSessionResponse = // Assuming this type is generated
  components["schemas"]["CustomerPortalSessionResponse"];
type SubscriptionRead = components["schemas"]["SubscriptionRead"];

// API prefix for billing endpoints
const BILLING_API_PREFIX = "/api/v1/billing";

/**
 * Creates a Stripe Checkout session for a user to subscribe to a selected plan.
 * The response includes a URL to redirect the user to Stripe's checkout page.
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {CreateCheckoutSessionRequest} payload - The data containing the price_id.
 * @returns {Promise<CreateCheckoutSessionResponse>} A promise that resolves with the checkout session ID, URL, and publishable key.
 * @throws {Error} If the API call fails or returns a non-OK status.
 */
export const createCheckoutSession = async (
  fetcher: FetchFunction,
  payload: CreateCheckoutSessionRequest
): Promise<CreateCheckoutSessionResponse> => {
  const endpoint = `${BILLING_API_PREFIX}/create-checkout-session`;
  console.log(
    `[API Client] Creating Stripe Checkout session, endpoint: ${endpoint}, payload:`,
    payload
  );

  try {
    const response = await fetcher(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Non-JSON error response
      }
      throw new Error(
        `Failed to create Stripe Checkout session: ${errorDetail}`
      );
    }

    const data: CreateCheckoutSessionResponse = await response.json();
    console.log(
      "[API Client] Successfully created Stripe Checkout session:",
      data
    );
    return data;
  } catch (error) {
    console.error("[API Client] Error in createCheckoutSession:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(
      "An unknown error occurred while creating the Stripe Checkout session."
    );
  }
};

/**
 * Creates a Stripe Customer Portal session for an authenticated user to manage their subscription.
 * The response includes a URL to redirect the user to Stripe's customer portal.
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @returns {Promise<CustomerPortalSessionResponse>} A promise that resolves with the URL to the Customer Portal.
 * @throws {Error} If the API call fails or returns a non-OK status.
 */
export const createCustomerPortalSession = async (
  fetcher: FetchFunction
): Promise<CustomerPortalSessionResponse> => {
  const endpoint = `${BILLING_API_PREFIX}/create-customer-portal-session`;
  console.log(
    `[API Client] Creating Stripe Customer Portal session, endpoint: ${endpoint}`
  );

  try {
    const response = await fetcher(endpoint, {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
      // No body needed if the backend derives customer_id from the authenticated user
    });

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Non-JSON error response
      }
      throw new Error(
        `Failed to create Stripe Customer Portal session: ${errorDetail}`
      );
    }

    const data: CustomerPortalSessionResponse = await response.json();
    console.log(
      "[API Client] Successfully created Stripe Customer Portal session:",
      data
    );
    return data;
  } catch (error) {
    console.error("[API Client] Error in createCustomerPortalSession:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(
      "An unknown error occurred while creating the Stripe Customer Portal session."
    );
  }
};

/**
 * Fetches the current active or trialing subscription details for the authenticated user.
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @returns {Promise<SubscriptionRead | null>}
 *          A promise that resolves with the subscription details or null if no active/trialing subscription is found.
 * @throws {Error} If the API call fails or returns a non-OK status (other than 404).
 */
export const getMySubscription = async (
  fetcher: FetchFunction
): Promise<SubscriptionRead | null> => {
  const endpoint = `${BILLING_API_PREFIX}/my-subscription`;
  console.log(
    `[API Client] Fetching current subscription, endpoint: ${endpoint}`
  );

  try {
    const response = await fetcher(endpoint, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (response.status === 404) {
      console.log(
        "[API Client] No active or trialing subscription found for the user (404)."
      );
      return null; // Treat 404 as "no active subscription"
    }

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Non-JSON error response
      }
      throw new Error(`Failed to fetch subscription details: ${errorDetail}`);
    }

    const data: SubscriptionRead = await response.json();
    console.log(
      "[API Client] Successfully fetched subscription details:",
      data
    );
    return data;
  } catch (error) {
    console.error("[API Client] Error in getMySubscription:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(
      "An unknown error occurred while fetching subscription details."
    );
  }
};
