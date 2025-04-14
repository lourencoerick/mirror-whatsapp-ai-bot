/* eslint-disable @typescript-eslint/no-unused-vars */
import {
    Inbox,
    InboxCreatePayload,
    InboxUpdatePayload,
  } from '@/types/inbox'; 
  import { FetchFunction } from '@/hooks/use-authenticated-fetch'; 
  
  const API_V1_BASE = '/api/v1'; 
  
  /**
   * Fetches the list of inboxes for the current account.
   * @param {FetchFunction} fetcher - The authenticated fetch function instance.
   * @param {number} [limit=100] - Max number of inboxes to return.
   * @param {number} [offset=0] - Number of inboxes to skip.
   * @returns {Promise<Inbox[]>} A promise that resolves to an array of inboxes.
   * @throws {Error} If the network request fails or the API returns an error status.
   */
  export const fetchInboxes = async (
    fetcher: FetchFunction,
    limit: number = 100,
    offset: number = 0
  ): Promise<Inbox[]> => {
    const endpoint = `${API_V1_BASE}/inboxes?limit=${limit}&offset=${offset}`;
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
        /* Ignore parsing error */
      }
      throw new Error(`Failed to fetch inboxes: ${errorDetail}`);
    }
  
    const data: Inbox[] = await response.json();
    return data;
  };
  
  /**
   * Fetches a single inbox by its ID.
   * @param {string} inboxId - The ID of the inbox to fetch.
   * @param {FetchFunction} fetcher - The authenticated fetch function instance.
   * @returns {Promise<Inbox>} A promise resolving to the inbox details.
   * @throws {Error} If the network request fails, inbox not found, or API returns an error.
   */
  export const getInboxById = async (
    inboxId: string,
    fetcher: FetchFunction
  ): Promise<Inbox> => {
    if (!inboxId) {
      throw new Error('Inbox ID is required.');
    }
    const endpoint = `${API_V1_BASE}/inboxes/${inboxId}`;
    const response = await fetcher(endpoint, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });
  
    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      if (response.status === 404) {
        errorDetail = 'Inbox not found';
      } else {
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          /* Ignore parsing error */
        }
      }
      throw new Error(`Failed to fetch inbox ${inboxId}: ${errorDetail}`);
    }
  
    const data: Inbox = await response.json();
    return data;
  };
  
  /**
   * Creates a new inbox.
   * @param {InboxCreatePayload} payload - The data for the new inbox.
   * @param {FetchFunction} fetcher - The authenticated fetch function instance.
   * @returns {Promise<Inbox>} A promise resolving to the newly created inbox.
   * @throws {Error} If the network request fails or the API returns an error status.
   */
  export const createInbox = async (
    payload: InboxCreatePayload,
    fetcher: FetchFunction
  ): Promise<Inbox> => {
    const endpoint = `${API_V1_BASE}/inboxes`;
    const response = await fetcher(endpoint, {
      method: 'POST',
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
      } catch (e) {
        /* Ignore parsing error */
      }
      throw new Error(`Failed to create inbox: ${errorDetail}`);
    }
  
    // Expecting 201 Created status, response body contains the new inbox
    const data: Inbox = await response.json();
    return data;
  };
  
  /**
   * Updates an existing inbox.
   * @param {string} inboxId - The ID of the inbox to update.
   * @param {InboxUpdatePayload} payload - The update data.
   * @param {FetchFunction} fetcher - The authenticated fetch function instance.
   * @returns {Promise<Inbox>} A promise resolving to the updated inbox details.
   * @throws {Error} If the network request fails, inbox not found, or API returns an error.
   */
  export const updateInbox = async (
    inboxId: string,
    payload: InboxUpdatePayload,
    fetcher: FetchFunction
  ): Promise<Inbox> => {
    if (!inboxId) {
      throw new Error('Inbox ID is required for update.');
    }
    const endpoint = `${API_V1_BASE}/inboxes/${inboxId}`;
    const response = await fetcher(endpoint, {
      method: 'PUT', // Assuming PUT for updates based on your backend router
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  
    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      if (response.status === 404) {
        errorDetail = 'Inbox not found';
      } else {
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          /* Ignore parsing error */
        }
      }
      throw new Error(`Failed to update inbox ${inboxId}: ${errorDetail}`);
    }
  
    const data: Inbox = await response.json();
    return data;
  };
  
  /**
   * Deletes an inbox by its ID.
   * @param {string} inboxId - The ID of the inbox to delete.
   * @param {FetchFunction} fetcher - The authenticated fetch function instance.
   * @returns {Promise<void>} A promise that resolves when deletion is successful.
   * @throws {Error} If the network request fails, inbox not found, or API returns an error.
   */
  export const deleteInbox = async (
    inboxId: string,
    fetcher: FetchFunction
  ): Promise<void> => {
    if (!inboxId) {
      throw new Error('Inbox ID is required for deletion.');
    }
    const endpoint = `${API_V1_BASE}/inboxes/${inboxId}`;
    const response = await fetcher(endpoint, {
      method: 'DELETE',
      headers: {
        Accept: 'application/json', // Even if no content, good practice
      },
    });
  
    // Expecting 204 No Content for successful deletion
    if (response.status === 204) {
      return; // Success
    }
  
    // Handle other statuses as errors
    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      if (response.status === 404) {
        errorDetail = 'Inbox not found';
      } else {
        try {
          // Attempt to parse error detail, but DELETE might not have a body
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          /* Ignore parsing error */
        }
      }
      throw new Error(`Failed to delete inbox ${inboxId}: ${errorDetail}`);
    }
  
    // Should not happen if status is 204, but as a fallback
    if (response.ok && response.status !== 204) {
       console.warn(`Delete request for inbox ${inboxId} returned status ${response.status} instead of 204, but was 'ok'.`);
       return;
    }
  };