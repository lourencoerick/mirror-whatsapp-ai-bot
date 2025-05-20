export interface Message {
  id: string;
  content: string;
  direction: "in" | "out";
  content_type: string;
  sent_at: string;
  created_at: string;
  updated_at: string;
}

export interface MessageSocketEvent {
  type: string;
  payload: Message;
}
