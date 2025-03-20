import React from 'react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { User } from 'lucide-react'
import Link from 'next/link';
import clsx from 'clsx';


type Props = {
  id: string
  phoneNumber: string
  name: string
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
          <AvatarImage src={props.imageUrl} alt={props.name} />
          <AvatarFallback>
            <User />
          </AvatarFallback>
        </Avatar>
        <div className='flex flex-col flex-1'>
          <div className='flex flex-row justify-between gap-2'>
            <h4 className='text-sm truncate'><span>{`${props.phoneNumber} | ${props.name}`} </span></h4>
            <p className='text-sm text-muted-foreground truncate'>{props.lastMessageTime}</p>
          </div>

          <p className='text-sm text-muted-foreground truncate'>{props.lastMessage}</p>
        </div>
      </div>
    </Link>
  )
}

export default ConversationItem