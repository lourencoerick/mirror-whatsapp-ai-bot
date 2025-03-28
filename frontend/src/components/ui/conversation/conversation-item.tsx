import React from 'react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { User } from 'lucide-react'
import Link from 'next/link';
import clsx from 'clsx';
import { formatLastMessageAt } from "@/lib/utils/date-utils"
import { formatPhoneNumber } from "@/lib/utils/phone-utils"
import { truncateText } from "@/lib/utils/text-utils"
type Props = {
  id: string
  phoneNumber: string
  contactName: string
  lastMessage: string
  lastMessageTime: string
  imageUrl: string
  isSelected: boolean
}


const ConversationItem: React.FC<Props> = (props: Props) => {
  return (

    <Link href={`/dashboard/conversations/${props.id}`} className="block">
      <div
        className={clsx(
          'flex flex-row items-center px-2 gap-2 truncate border-t border-gray-200 h-20',
          props.isSelected ? 'bg-background' : 'hover:bg-gray-100'
        )}
      >
        <Avatar>
          <AvatarImage src={props.imageUrl} alt={props.contactName} />
          <AvatarFallback>
            <User />
          </AvatarFallback>
        </Avatar>
        <div className='flex flex-col flex-1 min-w-0'>
          <div className='flex flex-row justify-between gap-2'>
            <h4 className='text-sm truncate'><span>{truncateText(`${formatPhoneNumber(props.phoneNumber)} | ${props.contactName}`, 30)} </span></h4>
            {props.lastMessageTime && <p className='text-xs text-muted-foreground truncate'>{formatLastMessageAt(props.lastMessageTime)}</p>}
                        
          </div>

          <p className='text-sm text-muted-foreground truncate'>{truncateText(props.lastMessage, 30)}</p>
        </div>
      </div>
    </Link>
  )
}

export default ConversationItem