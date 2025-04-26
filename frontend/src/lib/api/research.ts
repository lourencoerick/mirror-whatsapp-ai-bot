// services/api/research.ts
import { FetchFunction } from '@/hooks/use-authenticated-fetch'; // Adjust path
import { components } from '@/types/api'; // Import from the generated types file

// Define type aliases for better readability
type ResearchRequest = components['schemas']['ResearchRequest'];
type ResearchResponse = components['schemas']['ResearchResponse'];
type ResearchJobStatusResponse = components['schemas']['ResearchJobStatusResponse']; // Assuming this name was generated

const API_V1_BASE = '/api/v1';

/**
 * Starts the company profile research task.
 * @param fetcher The authenticated fetch function.
 * @param url The website URL to research.
 * @returns The response containing the job ID.
 * @throws Error on network or API errors.
 */
export const startResearch = async (
    fetcher: FetchFunction,
    url: string
): Promise<ResearchResponse> => { // Use generated type for return
    const endpoint = `${API_V1_BASE}/research/start`;
    // Use generated type for payload structure validation (though it's simple here)
    const payload: ResearchRequest = { url };

    const response = await fetcher(endpoint, {
        method: 'POST',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (response.status !== 202 || !response.ok) {
        let errorDetail = `API returned status ${response.status}`;
        try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ }
        throw new Error(`Failed to start research: ${errorDetail}`);
    }

    const data: ResearchResponse = await response.json(); // Use generated type
    return data;
};

/**
 * Gets the status of a research job.
 * @param fetcher The authenticated fetch function.
 * @param jobId The ID of the job to check.
 * @returns The job status response.
 * @throws Error on network or API errors.
 */
export const getResearchJobStatus = async (
    fetcher: FetchFunction,
    jobId: string
): Promise<ResearchJobStatusResponse> => { // Use generated type for return
    if (!jobId) {
        throw new Error('Job ID is required to check status.');
    }
    const endpoint = `${API_V1_BASE}/research/status/${jobId}`;
    const response = await fetcher(endpoint, {
        method: 'GET',
        headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
        let errorDetail = `API returned status ${response.status}`;
        if (response.status === 404) errorDetail = 'Job not found';
        else { try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ } }
        throw new Error(`Failed to get job status for ${jobId}: ${errorDetail}`);
    }

    const data: ResearchJobStatusResponse = await response.json(); // Use generated type
    return data;
};