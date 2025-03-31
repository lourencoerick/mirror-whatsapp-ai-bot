// src/hooks/useAuthenticatedFetch.ts
import { useCallback } from 'react';
import { useAuth } from '@clerk/nextjs'; // Import the hook from Clerk
import { log } from 'next-axiom';

/**
 * Interface for fetch options, extending the standard RequestInit.
 */
interface AuthenticatedFetchOptions extends RequestInit {}

/**
 * Type definition for the fetch function returned by the hook.
 */
type FetchFunction = (
    url: string,
    options?: AuthenticatedFetchOptions
) => Promise<Response>;

/**
 * Custom hook that provides a fetch function pre-configured with
 * the Clerk authentication token.
 * Automatically retrieves the token using useAuth().getToken().
 *
 * @returns {FetchFunction} An async function compatible with the fetch API.
 */
export function useAuthenticatedFetch(): FetchFunction {
  // Get functions and state from Clerk's useAuth hook
  const { getToken, isLoaded, isSignedIn, signOut } = useAuth();

  // Use useCallback to memoize the fetchWrapper function.
  // It will only be recreated if one of the dependencies (getToken, etc.) changes.
  const fetchWrapper = useCallback(async (
    url: string,
    options: AuthenticatedFetchOptions = {}
  ): Promise<Response> => {

    // 1. Check if Clerk has loaded the authentication state
    if (!isLoaded) {
        const warningMessage = "[useAuthenticatedFetch] Clerk auth state not loaded yet. Request blocked.";
        console.warn(warningMessage);
        log.warn(warningMessage);
        // Return a simulated error response or throw an exception
        // Throwing an exception might be better for the caller to handle
        throw new Error("Authentication state not ready.");
    }

    // 2. Check if the user is signed in
    if (!isSignedIn) {
        const errorMessage = "[useAuthenticatedFetch] User is not signed in. Request blocked.";
        console.error(errorMessage);
        log.error(errorMessage);
        // Redirect to login or throw an error
        // Throwing allows the component to decide how to handle it
        throw new Error("User is not authenticated.");
    }

    // 3. Get the JWT token from Clerk
    const token = await getToken({ template: "fastapi-backend" }); // Call the function from the useAuth hook

    // 4. Check if the token was successfully retrieved
    if (!token) {
      const errorMessage = "[useAuthenticatedFetch] Authentication token could not be retrieved from Clerk.";
      console.error(errorMessage);
      log.error(errorMessage);
      throw new Error('Authentication token could not be retrieved.');
    }

    // 5. Prepare the Request Headers
    const headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${token}`); // Add the Bearer token
    // Ensure Content-Type for requests with a body (POST, PUT, PATCH)
    if (options.body && !headers.has('Content-Type')) {
       headers.set('Content-Type', 'application/json'); // Assume JSON by default
    }

    // 6. Construct the Full Backend URL
    // Read the backend base URL from frontend environment variables
    const backendApiUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000'; // Default for local dev
    // Ensure the final URL is absolute
    const fullUrl = url.startsWith('http') ? url : (url.startsWith('/') ? `${backendApiUrl}${url}` : `${backendApiUrl}/${url}`);

    // 7. Execute the Fetch Request
    try {
       const requestInfo = `[useAuthenticatedFetch] Requesting: ${options.method || 'GET'} ${fullUrl}`;
       console.log(requestInfo);
       log.debug(requestInfo);

       const response = await fetch(fullUrl, {
           ...options, // Include method, body, etc.
           headers: headers, // Pass the configured headers
       });

       const responseInfo = `[useAuthenticatedFetch] Response Status: ${response.status} for ${fullUrl}`;
       console.log(responseInfo);
       log.debug(responseInfo);

       // 8. Specific Handling for Authentication/Authorization Errors (401/403)
       if (response.status === 401) {
           const errorDetail = "[useAuthenticatedFetch] Received 401 Unauthorized. Token might be expired or invalid.";
           console.error(errorDetail);
           log.error(errorDetail);
           await signOut(); // Use await if signOut is async
           throw new Error("Unauthorized: Invalid or expired token.");
       }
        if (response.status === 403) {
           const errorDetail = "[useAuthenticatedFetch] Received 403 Forbidden. User may not have permission or account not provisioned.";
           console.error(errorDetail);
           log.error(errorDetail);
           // Throw error for the component to handle (e.g., show "Access Denied" message)
           throw new Error("Forbidden: Access denied.");
       }

       // 9. Return the Response to the Caller
       return response;

    } catch (error) {
       // Catch network errors or errors thrown during 401/403 handling
       const networkErrorInfo = `[useAuthenticatedFetch] Network or fetch error for ${fullUrl}:`;
       console.error(networkErrorInfo, error);
       log.error(networkErrorInfo, { error });
       throw error; // Re-throw the error for the calling component to handle
    }
  }, [getToken, isLoaded, isSignedIn, signOut]); // Dependencies for useCallback

  // Return the memoized fetchWrapper function
  return fetchWrapper;
}