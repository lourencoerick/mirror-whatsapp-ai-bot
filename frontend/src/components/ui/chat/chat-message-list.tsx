import * as React from "react";
interface ChatMessageListProps extends React.HTMLAttributes<HTMLDivElement> {
}

const ChatMessageList = React.forwardRef<HTMLDivElement, ChatMessageListProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={`w-full ${className || ''}`} {...props}>
          <div className="flex flex-col gap-2 md:gap-4">
            {children}
          </div>
      </div>
    );
  }
);

ChatMessageList.displayName = "ChatMessageList";

export { ChatMessageList };