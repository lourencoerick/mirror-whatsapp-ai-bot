'use server';

import api from '@/lib/api';
import { revalidatePath } from 'next/cache';
import { auth } from '@clerk/nextjs/server';

interface StartConversationPayload {
  phoneNumber: string;
  inboxId: string;
}

interface StartConversationResult {
  success: boolean;
  conversation_id?: string;
  error?: string;
}

/**
 * Starts a new conversation for a given inbox and phone number.
 *
 * This function posts to the `/inboxes/:inboxId/conversations` endpoint.
 * It now uses Clerk for authentication and includes the JWT token in the request.
 *
 * @param payload - An object containing:
 *   - `phoneNumber`: The phone number to start the conversation with.
 *   - `inboxId`: The ID of the inbox where the conversation should be created.
 *
 * @returns A Promise resolving to a result object containing the new conversation ID or an error message.
 */
export async function startConversation({
  phoneNumber,
  inboxId,
}: StartConversationPayload): Promise<StartConversationResult> {
  try {
    const { userId, getToken } = await auth(); // Get Clerk auth

    if (!userId) {
      console.warn('[startConversation] Unauthorized access attempt.');
      return { success: false, error: 'Unauthorized' };
    }

    const token = await getToken({ template: 'fastapi-backend' });

    if (!token) {
      console.error('[startConversation] Could not generate token.');
      return { success: false, error: 'Could not generate token' };
    }

    console.log('[startConversation] Creating a new conversation...');
    const response = await api.post(
      `/api/v1/inboxes/${inboxId}/conversations`,
      {
        phone_number: phoneNumber,
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    const data = response.data;
    revalidatePath(`/dashboard/conversations/${data.conversation_id}`);

    return { success: true, conversation_id: data.conversation_id };
  } catch (e: any) {
    console.error('[startConversation] Error:', e);
    return { success: false, error: e.message };
  }
}