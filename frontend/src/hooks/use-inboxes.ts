import { useState, useEffect } from 'react';
import { AxiosResponse } from 'axios';
import api from '@/lib/api';

export interface Inbox {
  id: string;
  name: string;
  channel_type: string;
  channel_id: string;
}

/**
 * Custom hook to fetch inboxes for the current user.
 *
 * This hook calls `/inboxes` and provides loading/error state.
 *
 * @returns Object with inbox list, loading flag, and error state.
 */
export function useInboxes(): {
  inboxes: Inbox[];
  loading: boolean;
  error: boolean;
} {
  const [inboxes, setInboxes] = useState<Inbox[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    async function fetchInboxes(): Promise<void> {
      try {
        setLoading(true);
        const res: AxiosResponse<Inbox[]> = await api.get('/inboxes');
        setInboxes(res.data);
      } catch (err: unknown) {
        console.error('Error fetching inboxes', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    }

    fetchInboxes();
  }, []);

  return { inboxes, loading, error };
}