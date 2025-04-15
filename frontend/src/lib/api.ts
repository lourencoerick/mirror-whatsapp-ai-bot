import axios, { InternalAxiosRequestConfig } from 'axios';
import { getClientAuthToken } from './get-token';
import qs from 'qs';

const backendApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: backendApiUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: params => qs.stringify(params, { arrayFormat: 'repeat' }),
});

// Axios Request Interceptor
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Define routes that should NOT get the auth token
    const publicRoutes = ['/webhooks/'];
    const isPublicRoute = publicRoutes.some(route => config.url?.startsWith(route));

    if (config.url === '/api/token' || isPublicRoute || config.headers.Authorization) {
      console.log(`[Axios Interceptor] Public route or token route ${config.url}, skipping token.`);
      return config;
    }

    console.log(`[Axios Interceptor] Adding token for ${config.url}`);
    const token = await getClientAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.error('[Axios Interceptor] Token not available.');
    }

    console.log(`[Axios Interceptor] Final Request:`, {
      method: config.method,
      headers: config.headers,
      params: config.params,
      data: config.data,
    });

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
        console.error("Unauthorized access - possibly expired token.");
      } else if (error.response.status === 403) {
        console.error("Forbidden access - user may lack permissions.");
      }
    } else if (error.request) {
      console.error('[Axios Interceptor] No response received:', error.request);
    } else {
      console.error('[Axios Interceptor] Error setting up request:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
