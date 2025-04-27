/* eslint-disable @typescript-eslint/no-unused-vars */
// services/api/profile.ts

import { FetchFunction } from '@/hooks/use-authenticated-fetch';
import { components } from '@/types/api';
type CompanyProfileSchemaOutput = components['schemas']['CompanyProfileSchema-Output'];
type CompanyProfileSchemaInput = components['schemas']['CompanyProfileSchema-Input'];


const API_V1_BASE = '/api/v1';

/**
 * Fetches the company profile for the current account.
 * @param fetcher The authenticated fetch function.
 * @returns The company profile data or null if not found.
 * @throws Error on network or API errors (excluding 404).
 */
export const getCompanyProfile = async (
  fetcher: FetchFunction
): Promise<CompanyProfileSchemaOutput | null> => {
  const endpoint = `${API_V1_BASE}/profile`;
  const response = await fetcher(endpoint, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });

  if (response.status === 404) {
    console.log('Company profile not found for this account.');
    return null;
  }

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) { /* Ignore */ }
    throw new Error(`Failed to fetch company profile: ${errorDetail}`);
  }

  const data: CompanyProfileSchemaOutput = await response.json();
  return data;
};

/**
 * Updates or creates the company profile for the current account.
 * @param fetcher The authenticated fetch function.
 * @param profileData The profile data to save.
 * @returns The saved company profile data.
 * @throws Error on network or API errors.
 */
export const updateCompanyProfile = async (
  fetcher: FetchFunction,
  profileData: CompanyProfileSchemaInput // Use the schema directly
): Promise<CompanyProfileSchemaOutput> => {
  const endpoint = `${API_V1_BASE}/profile`;
  const payload = { ...profileData };
  // Ensure ID is not sent if present, backend handles creation/update logic
  if ('id' in payload && payload.id === undefined) {
      delete payload.id;
  }

  const response = await fetcher(endpoint, {
    method: 'PUT',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
     let errorDetail = `API returned status ${response.status}`;
     try {
       const errorData = await response.json();
       errorDetail = errorData.detail || errorDetail;
     } catch (e) { /* Ignore */ }
     throw new Error(`Failed to update company profile: ${errorDetail}`);
  }

  const data: CompanyProfileSchemaOutput = await response.json();
  return data;
};