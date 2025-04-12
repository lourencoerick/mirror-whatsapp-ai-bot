export enum ConversationStatusEnum {
  OPEN = "OPEN",
  PENDING = "PENDING",
  HUMAN_ACTIVE = "HUMAN_ACTIVE",
  CLOSED = "CLOSED",
}
export interface Conversation {
  id: string;

  status: ConversationStatusEnum;
  unread_agent_count: number;  
  
  contact: {
    name?: string | null;    
    phone_number: string;
    profile_picture_url?: string | null;
  } | null;
  updated_at: string;
  last_message_at?: string | null;
  last_message: {
    id: string;
    content?: string | null;
    sent_at?: string | null;
  } | null;

  matching_message: {
    id: string;
    content?: string | null;
    sent_at?: string | null;
  } | null;  
}


export interface ConversationSocketEvent {
  type: 'new_conversation' | 'conversation_updated';
  payload: Conversation;
}


export interface UseInfiniteConversationsResult {
  conversations: Conversation[];
  loading: boolean;
  error: boolean;
  hasMore: boolean;
  loadMore: () => void;
}