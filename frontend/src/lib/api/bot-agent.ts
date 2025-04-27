/* eslint-disable @typescript-eslint/no-unused-vars */
// services/api/botAgent.ts
import { FetchFunction } from '@/hooks/use-authenticated-fetch'; // Adjust path
import { components } from '@/types/api'; // Import from the generated types file

// Define type aliases for better readability using the generated types
type BotAgentRead = components['schemas']['BotAgentRead'];
type BotAgentUpdate = components['schemas']['BotAgentUpdate'];
type AgentInboxAssociationUpdate = components['schemas']['AgentInboxAssociationUpdate'];
type InboxRead = components['schemas']['InboxRead']; // Assuming InboxRead is generated

const API_V1_BASE = '/api/v1';

/**
 * Fetches the Bot Agent for the current account.
 * Assumes one agent per account (takes the first from the list).
 * @param fetcher The authenticated fetch function.
 * @returns The BotAgent data or null if not found.
 * @throws Error on network or API errors.
 */
export const getMyBotAgent = async (
    fetcher: FetchFunction
): Promise<BotAgentRead | null> => {
    const endpoint = `${API_V1_BASE}/bot-agents/`;
    const response = await fetcher(endpoint, {
        method: 'GET',
        headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
        let errorDetail = `API returned status ${response.status}`;
        try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ }
        throw new Error(`Failed to fetch bot agents: ${errorDetail}`);
    }

    // The API returns a list, use the generated type for the list item
    const data: BotAgentRead[] = await response.json();
    if (data && data.length > 0) {
        return data[0]; // Return the first agent
    } else {
        console.log('No Bot Agent found for this account.');
        return null;
    }
};

/**
 * Updates the Bot Agent for the current account.
 * @param fetcher The authenticated fetch function.
 * @param agentId The ID of the agent to update.
 * @param agentData The partial update data matching BotAgentUpdate schema.
 * @returns The updated BotAgent data.
 * @throws Error on network or API errors.
 */
export const updateMyBotAgent = async (
    fetcher: FetchFunction,
    agentId: string, // UUID as string
    agentData: BotAgentUpdate // Use the generated type
): Promise<BotAgentRead> => { // Return type uses generated type
    const endpoint = `${API_V1_BASE}/bot-agents/${agentId}`;
    const response = await fetcher(endpoint, {
        method: 'PUT',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(agentData),
    });

    if (!response.ok) {
        let errorDetail = `API returned status ${response.status}`;
        if (response.status === 404) errorDetail = 'Bot Agent not found';
        else { try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ } }
        throw new Error(`Failed to update bot agent ${agentId}: ${errorDetail}`);
    }

    const data: BotAgentRead = await response.json(); // Use the generated type
    return data;
};

/**
 * Sets the associated inboxes for a specific Bot Agent.
 * @param fetcher The authenticated fetch function.
 * @param agentId The ID of the agent.
 * @param inboxIds An array of Inbox UUIDs (as strings) to associate.
 * @returns {Promise<void>} Resolves on success.
 * @throws Error on network or API errors.
 */
export const setAgentInboxes = async (
    fetcher: FetchFunction,
    agentId: string,
    inboxIds: string[] // Keep as string array for input
): Promise<void> => {
    const endpoint = `${API_V1_BASE}/bot-agents/${agentId}/inboxes`;
    // Use the generated type for the payload structure
    const payload: AgentInboxAssociationUpdate = { inbox_ids: inboxIds };

    const response = await fetcher(endpoint, {
        method: 'PUT',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (response.status === 204) {
        return; // Success
    }

    let errorDetail = `API returned status ${response.status}`;
    if (response.status === 404) errorDetail = 'Bot Agent not found';
    else { try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ } }
    throw new Error(`Failed to set agent inboxes for ${agentId}: ${errorDetail}`);
};

/**
 * Fetches the Inboxes associated with a specific Bot Agent.
 * @param fetcher The authenticated fetch function.
 * @param agentId The ID of the agent.
 * @returns A list of associated Inbox data.
 * @throws Error on network or API errors.
 */
export const getAgentInboxes = async (
    fetcher: FetchFunction,
    agentId: string
): Promise<InboxRead[]> => { // Use the generated InboxRead type
     const endpoint = `${API_V1_BASE}/bot-agents/${agentId}/inboxes`;
     const response = await fetcher(endpoint, {
         method: 'GET',
         headers: { Accept: 'application/json' },
     });

     if (!response.ok) {
        let errorDetail = `API returned status ${response.status}`;
        if (response.status === 404) errorDetail = 'Bot Agent not found';
        else { try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore */ } }
        throw new Error(`Failed to get agent inboxes for ${agentId}: ${errorDetail}`);
     }

     const data: InboxRead[] = await response.json(); // Use the generated type
     return data;
};