'use client'; // Required for using hooks like useRouter

import Link from 'next/link';
import React from 'react';
import { useRouter } from 'next/navigation'; // Use 'next/navigation' for App Router
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User } from 'lucide-react';
import clsx from 'clsx';
import { formatLastMessageAt } from "@/lib/utils/date-utils";
import { formatPhoneNumber } from "@/lib/utils/phone-utils";
import { truncateText } from "@/lib/utils/text-utils";

type ConversationItemProps = {
  id: string;
  phoneNumber?: string;
  contactName?: string;
  lastMessageContent?: string;
  lastMessageTime?: string;
  imageUrl?: string;
  isSelected?: boolean;
  matchingMessageId?: string;
  matchingMessageContent?: string;

};

const ConversationItem: React.FC<ConversationItemProps> = ({
  id,
  phoneNumber = '',
  contactName = '',
  lastMessageContent = '',
  lastMessageTime,
  imageUrl = '',
  isSelected = false,
  matchingMessageId,
  matchingMessageContent,
}) => {
  const router = useRouter();

  const handleItemClick = () => {
    // Base URL for the conversation chat page
    const chatUrl = `/dashboard/conversations/${id}`;

    // Conditionally add the highlight query parameter
    const finalUrl = matchingMessageId
      ? `${chatUrl}?highlight=${matchingMessageId}`
      : chatUrl;

    console.log(`Navigating to: ${finalUrl}`);
    router.push(finalUrl);
  };
  console.log(`Rendering matching with ID: ${matchingMessageId}`);

  // Format display values (moved logic here for clarity)
  const displayPhoneNumber = formatPhoneNumber(phoneNumber);
  const displayName = contactName? `| ${contactName}` : '';
  const displayTitle = truncateText(`${displayPhoneNumber} ${displayName}`, 25);
  const displayMessage = matchingMessageId? truncateText(matchingMessageContent, 30) :truncateText(lastMessageContent, 30);
  const displayTime = lastMessageTime ? formatLastMessageAt(lastMessageTime) : '';


  const isMatchResult = !!matchingMessageId;

  return (
      <div
        onClick={handleItemClick}
        className={clsx(
          'flex flex-row items-center px-2 gap-2 truncate border-t border-gray-200 h-20  cursor-pointer',
          isSelected ? 'bg-background' : 'hover:bg-gray-100'
        )}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleItemClick()}
      >
        <Avatar>
          <AvatarImage src={imageUrl} alt={contactName} />
          <AvatarFallback>
            <User />
          </AvatarFallback>
        </Avatar>
        <div className='flex flex-col flex-1 min-w-0'>
          <div className='flex flex-row justify-between gap-2'>
            <h4 className='text-xs truncate'>
              <span>{displayTitle}</span>
            </h4>
            {displayTime && <p className='text-xs text-muted-foreground truncate'>{displayTime}</p>}
          </div>
          {/* Apply different style if it's a search result match */}
          <p className={clsx(
            'text-xs truncate',
            isMatchResult ? 'text-blue-600 font-medium' : 'text-muted-foreground' // Conditional styling
          )}>
            {isMatchResult ? `Encontrado: ${displayMessage}` : displayMessage} 
          </p>
        </div>
      </div>
  );
};

export default ConversationItem;