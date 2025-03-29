'use server';

import api from '@/lib/api'
import { revalidatePath } from 'next/cache'

interface StartConversationPayload {
  phoneNumber: string
  inboxId: string
}

interface StartConversationResult {
  success: boolean
  conversation_id?: string
  error?: string
}

/**
 * Starts a new conversation for a given inbox and phone number.
 *
 * This function posts to the `/inboxes/:inboxId/conversations` endpoint.
 *
 * @param payload - An object containing:
 *   - `phoneNumber`: The phone number to start the conversation with.
 *   - `inboxId`: The ID of the inbox where the conversation should be created.
 *
 * @returns A Promise resolving to a result object containing the new conversation ID or an error message.
 */
export async function startConversation({ phoneNumber, inboxId }: StartConversationPayload): Promise<StartConversationResult> {
  try {
    const response = await api.post(`/inboxes/${inboxId}/conversations`, {
      phone_number: phoneNumber,
    });

    const data = response.data;
    revalidatePath(`/dashboard/conversations/${data.conversation_id}`);

    return { success: true, conversation_id: data.conversation_id };
  } catch (e) {
    return { success: false, error: (e as Error).message };
  }
}
