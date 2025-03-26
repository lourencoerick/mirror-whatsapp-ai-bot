import api from '@/lib/api';

interface SendMessagePayload {
  conversationId: string;
  content: string;
}

/**
 * Sends a new message to the specified conversation via the backend API.
 *
 * This function posts a message to the `/conversations/:id/messages` endpoint.
 *
 * @param payload - An object containing:
 *   - `conversationId`: The ID of the conversation to send the message to.
 *   - `content`: The text content of the message.
 * @returns A Promise that resolves when the message is successfully sent.
 * @throws An error if the API call fails.
 */
export async function sendMessage({ conversationId, content }: SendMessagePayload): Promise<void> {
  await api.post(`/conversations/${conversationId}/messages`, {
    content,
  });
}
