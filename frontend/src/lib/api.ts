import axios from 'axios';

// Create an Axios instance with a base URL configured via environment variables
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL, // Base URL from .env file
});

// Set a fixed header for account identification
api.defaults.headers.common['X-Account-ID'] = '11111111-1111-1111-1111-111111111111';

export default api;
