// src/lib/actions/send-messages.ts

import api from "@/lib/api";
import { components } from "@/types/api";

type MessageResponse = components["schemas"]["MessageResponse"];

interface SendMessagePayload {
  conversationId: string;
  content: string;
}

/**
 * Sends a new message as the logged-in agent/user to the specified conversation.
 *
 * This function posts a message to the `/conversations/:id/messages` endpoint
 * and returns the created message data from the API response.
 *
 * @param {SendMessagePayload} payload - An object containing conversationId and content.
 * @returns {Promise<MessageResponse>} A Promise resolving with the message data returned by the API.
 * @throws {Error} If the API call fails (network error or non-2xx status).
 */
export async function sendMessage({
  conversationId,
  content,
}: SendMessagePayload): Promise<MessageResponse> {
  try {
    const response = await api.post<MessageResponse>(
      `/api/v1/conversations/${conversationId}/messages`,
      { content }
    );

    return response.data;
  } catch (error: any) {
    console.error(
      `[API Client] Failed to send agent message to conversation ${conversationId}:`,
      error
    );

    const errorMessage =
      error.response?.data?.detail ||
      error.message ||
      "Unknown error sending message";
    throw new Error(errorMessage);
  }
}
