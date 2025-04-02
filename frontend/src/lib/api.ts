import axios, { InternalAxiosRequestConfig } from 'axios';
import { getClientAuthToken } from './get-token';


const backendApiUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: backendApiUrl,
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Axios Request Interceptor ---
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Define routes that should NOT get the auth token
    const publicRoutes = [
      '/webhooks/',
      // Add other public API routes if any (e.g., '/api/public-info')
    ];

    // Check if the request URL matches any public route
    // Use startsWith for prefix matching
    const isPublicRoute = publicRoutes.some(route => config.url?.startsWith(route));

    // Also skip if the request is for the token endpoint itself (if using baseURL) or for server side components w token
    if (config.url === '/api/token' || isPublicRoute || config.headers.Authorization) {
      console.log(`[Axios Interceptor] Public route or token route ${config.url}, skipping token.`);
      return config;
    }

    console.log(`[Axios Interceptor] Adding token for ${config.url}`);
    const token = await getClientAuthToken();

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.error('[Axios Interceptor] Token not available. Request might fail or be unauthorized.');
    }

    return config;
  },
  (error) => {
    console.error('[Axios Interceptor] Request setup error:', error);
    return Promise.reject(error);
  }
);


api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response) {
            console.error(`[Axios Interceptor] Response Error ${error.response.status}:`, error.response.data?.detail || error.response.data);
            if (error.response.status === 401) {
                console.error("Unauthorized access - possibly expired token. Consider redirecting to sign-in.");
                // Example: Trigger sign-out or redirect
                // window.location.href = '/sign-in?session_expired=true';
            } else if (error.response.status === 403) {
                console.error("Forbidden access - user may lack permissions or account not provisioned.");
            }
        } else if (error.request) {
            console.error('[Axios Interceptor] No response received:', error.request);
        } else {
            console.error('[Axios Interceptor] Error setting up request:', error.message);
        }
        return Promise.reject(error);
    }
);


export default api; // Export the configured instance