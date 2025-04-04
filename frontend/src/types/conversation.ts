export interface Conversation {
  id: string;
  profile_picture_url: string;
  phone_number: string;
  contact_name: string;
  updated_at: string;
  last_message_at: string;
  last_message: {
    id: string;
    content: string;
    sent_at: string;
  } | null;

  matching_message: {
    id: string;
    content: string;
    sent_at: string;
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