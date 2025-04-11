/**
 * Represents the structure of an Inbox object received from the API.
 */
export interface Inbox {
    id: string; // UUID represented as string in JSON
    account_id?: string; // UUID represented as string in JSON
    name: string;
    channel_type: string;
    channel_id?: string | null; // Optional identifier from the channel provider
    channel_details?: Record<string, any> | null; // Channel specific config
    enable_auto_assignment?: boolean; // Auto assignment setting
    created_at: string; // ISO 8601 date string
    updated_at: string; // ISO 8601 date string
  }
  
  /**
   * Payload for creating a new Inbox via the API.
   * Matches the backend InboxCreate schema.
   */
  export interface InboxCreatePayload {
    name: string;
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
    channel_type?: string;
    channel_details?: Record<string, any> | null;
    enable_auto_assignment?: boolean;
  }