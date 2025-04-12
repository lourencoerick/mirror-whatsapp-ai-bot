'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User } from 'lucide-react';
import clsx from 'clsx';
import { formatLastMessageAt } from "@/lib/utils/date-utils";
import { formatPhoneNumber } from "@/lib/utils/phone-utils";
import { truncateText } from "@/lib/utils/text-utils";
import { ConversationStatusEnum } from '@/types/conversation';

// Define props with unreadCount and status
type ConversationItemProps = {
  id: string;
  contactName?: string;
  phoneNumber?: string;
  imageUrl?: string;
  lastMessageContent?: string;
  lastMessageTime?: string;
  matchingMessageId?: string | null;
  matchingMessageContent?: string | null;
  isSelected?: boolean;
  unreadCount: number;
  status: ConversationStatusEnum;
};

const ConversationItem: React.FC<ConversationItemProps> = ({
  id,
  contactName = '',
  phoneNumber = '',
  imageUrl = '',
  lastMessageContent = '',
  lastMessageTime,
  matchingMessageId,
  matchingMessageContent,
  isSelected = false,
  unreadCount,
  status,
}) => {
  const router = useRouter();

  const handleItemClick = () => {
    const chatUrl = `/dashboard/conversations/${id}`;
    const finalUrl = matchingMessageId
      ? `${chatUrl}?highlight=${matchingMessageId}`
      : chatUrl;
    console.log(`Navigating to: ${finalUrl}`);
    router.push(finalUrl);
  };

  // Format display values
  const displayPhoneNumber = formatPhoneNumber(phoneNumber);
  const displayName = contactName ? `| ${contactName}` : '';
  const displayTitle = truncateText(`${displayPhoneNumber} ${displayName}`, 30);
  const displayMessage = matchingMessageId
    ? truncateText(matchingMessageContent ?? '', 35)
    : truncateText(lastMessageContent, 35);
  const displayTime = lastMessageTime ? formatLastMessageAt(lastMessageTime) : '';

  const isMatchResult = !!matchingMessageId;

  return (
    <div
      onClick={handleItemClick}
      className={clsx(
        'relative flex flex-row items-center px-2 gap-2 truncate border-t border-gray-200 h-20 cursor-pointer w-xs',
        isSelected
          ? 'bg-neutral-200 dark:bg-neutral-800'
          : 'hover:bg-gray-100 dark:hover:bg-neutral-700',
        status === ConversationStatusEnum.CLOSED && !isSelected ? 'opacity-70' : ''
      )}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleItemClick()}
    >
      {/* Avatar Section */}
      <Avatar className="h-10 w-10">
        <AvatarImage src={imageUrl} alt={contactName} />
        <AvatarFallback>
          <User className="h-5 w-5" />
        </AvatarFallback>
      </Avatar>

      {/* Text Content Section */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top Row: Title and Time */}
        <div className="flex flex-row justify-between items-center gap-2">
          <h4 className="text-sm font-medium truncate">
            <span>{displayTitle}</span>
          </h4>
          {displayTime && <p className="text-xs text-muted-foreground flex-shrink-0">{displayTime}</p>}
        </div>
        {/* Bottom Row: Message Snippet and Unread Count Badge */}
        <div className="flex items-center justify-between">
          <p
            className={clsx(
              'text-xs truncate flex-grow pr-1',
              isMatchResult ? 'text-blue-600 font-medium' : 'text-muted-foreground'
            )}
          >
            {isMatchResult ? `Encontrado: ${displayMessage}` : displayMessage}
          </p>
          {unreadCount > 0 && (
            <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-medium text-white flex-shrink-0">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConversationItem;
