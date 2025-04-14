/* eslint-disable @typescript-eslint/no-unused-vars */
import { EvolutionInstance } from '@/types/evolution-instance'; 
import { FetchFunction } from '@/hooks/use-authenticated-fetch'; 

const API_V1_BASE = '/api/v1/instances/evolution'; 

/**
 * Triggers a synchronization of the Evolution Instance status with the backend API,
 * updates the status in the database, and returns the updated instance details.
 *
 * @param {string} instanceId - The unique identifier (DB ID) of the EvolutionInstance record.
 * @param {FetchFunction} fetcher - The authenticated fetch function instance.
 * @returns {Promise<EvolutionInstance>} A promise resolving to the updated EvolutionInstance object.
 * @throws {Error} If the network request fails, the instance is not found,
 *                 configuration is missing, or communication with the Evolution API fails.
 */
export const syncEvolutionInstanceStatus = async (
  instanceId: string,
  fetcher: FetchFunction
): Promise<EvolutionInstance> => {
  if (!instanceId) {
    throw new Error('Evolution Instance ID is required.');
  }

  const endpoint = `${API_V1_BASE}/${instanceId}/status`;

  const response = await fetcher(endpoint, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
    }

    if (response.status === 404) {
      errorDetail = `Evolution Instance with ID '${instanceId}' not found or not accessible.`;
    } else if (response.status === 400) {
      errorDetail = `Bad request: ${errorDetail}. Check instance configuration.`;
    } else if (response.status === 502) {
      errorDetail = `Upstream error: Failed to communicate with the Evolution API. ${errorDetail}`;
    } else if (response.status === 504) {
      errorDetail = `Gateway Timeout: Could not connect to the Evolution API. ${errorDetail}`;
    }

    throw new Error(`Failed to sync instance status: ${errorDetail}`);
  }

  // If response.ok (status 200), parse the updated instance data
  const data: EvolutionInstance = await response.json();
  return data;
};
