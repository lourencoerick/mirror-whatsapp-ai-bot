/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Represents the structure of an Inbox object received from the API.
 */

import { components } from '@/types/api'; // Import from the generated types file
import { EvolutionInstanceStatus } from "@/types/evolution-instance";

export type ConversationStatusOption = 
| 'BOT'
| 'PENDING'
| 'OPEN'
| 'HUMAN_ACTIVE'
| 'CLOSED';

export type InboxRead = components['schemas']['InboxRead'];
  export interface Inbox extends InboxRead {
    connection_status: EvolutionInstanceStatus;
  }

  
  /**
   * Payload for creating a new Inbox via the API.
   * Matches the backend InboxCreate schema.
   */
  export interface InboxCreatePayload {
    name: string;
    initial_conversation_status: ConversationStatusOption;
    channel_type: string; // e.g., 'whatsapp'
    channel_details?: Record<string, any> | null;
    enable_auto_assignment?: boolean;
  }
  
  /**
   * Payload for updating an existing Inbox via the API.
   * Matches the backend InboxUpdate schema. All fields are optional.
   */
  export interface InboxUpdatePayload {
    name?: string;
    initial_conversation_status?: ConversationStatusOption;
    channel_type?: string;
    channel_details?: Record<string, any> | null;
    enable_auto_assignment?: boolean;
  }