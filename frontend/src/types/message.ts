export interface Message {
    id: string;
    content: string;
    direction: "in" | "out";
    message_type: string;
    content_type: string;
    sent_at: string;

}


export interface MessageSocketEvent {
    type: string;
    payload: Message;
}
