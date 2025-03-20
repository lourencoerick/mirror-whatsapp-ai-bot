'use client';

import React from 'react'

import { useParams } from 'next/navigation';
import ConversationItem from './conversation-item';
const mockedConversations = [
  {
    id: '1',
    phoneNumber: '+55 11 98765-4321',
    name: 'João Silva',
    lastMessage: 'Oi, como você está?',
    lastMessageTime: '10:30 AM',
    imageUrl: 'https://randomuser.me/api/portraits/men/1.jpg'
  },
  {
    id: '2',
    phoneNumber: '+55 21 91234-5678',
    name: 'Maria Oliveira',
    lastMessage: 'Enviado o documento que pediu!',
    lastMessageTime: 'Ontem',
    imageUrl: 'https://randomuser.me/api/portraits/women/2.jpg'
  },
  {
    id: '3',
    phoneNumber: '+1 305 555-0198',
    name: 'Carlos Eduardo',
    lastMessage: 'Vamos marcar a reunião para amanhã?',
    lastMessageTime: 'Segunda-feira',
    imageUrl: 'https://randomuser.me/api/portraits/men/3.jpg'
  },
  {
    id: '4',
    phoneNumber: '+33 6 22 33 44 55',
    name: 'Sophie Martin',
    lastMessage: 'Bonjour! Ça va?',
    lastMessageTime: 'Semana passada',
    imageUrl: 'https://randomuser.me/api/portraits/women/4.jpg'
  },
  {
    id: '5',
    phoneNumber: '+49 152 12345678',
    name: 'Lukas Schmidt',
    lastMessage: 'Vielen Dank! Bis später!',
    lastMessageTime: '2 semanas atrás',
    imageUrl: 'https://randomuser.me/api/portraits/men/5.jpg'
  },
  {
    id: '11',
    phoneNumber: '+55 11 98765-4321',
    name: 'João Silva',
    lastMessage: 'Oi, como você está?',
    lastMessageTime: '10:30 AM',
    imageUrl: 'https://randomuser.me/api/portraits/men/1.jpg'
  },
  {
    id: '12',
    phoneNumber: '+55 21 91234-5678',
    name: 'Maria Oliveira',
    lastMessage: 'Enviado o documento que pediu!',
    lastMessageTime: 'Ontem',
    imageUrl: 'https://randomuser.me/api/portraits/women/2.jpg'
  },
  {
    id: '13',
    phoneNumber: '+1 305 555-0198',
    name: 'Carlos Eduardo',
    lastMessage: 'Vamos marcar a reunião para amanhã?',
    lastMessageTime: 'Segunda-feira',
    imageUrl: 'https://randomuser.me/api/portraits/men/3.jpg'
  },
  {
    id: '14',
    phoneNumber: '+33 6 22 33 44 55',
    name: 'Sophie Martin',
    lastMessage: 'Bonjour! Ça va?',
    lastMessageTime: 'Semana passada',
    imageUrl: 'https://randomuser.me/api/portraits/women/4.jpg'
  },
  {
    id: '15',
    phoneNumber: '+49 152 12345678',
    name: 'Lukas Schmidt',
    lastMessage: 'Vielen Dank! Bis später!',
    lastMessageTime: '2 semanas atrás',
    imageUrl: 'https://randomuser.me/api/portraits/men/5.jpg'
  },
  {
    id: '21',
    phoneNumber: '+55 11 98765-4321',
    name: 'João Silva',
    lastMessage: 'Oi, como você está?',
    lastMessageTime: '10:30 AM',
    imageUrl: 'https://randomuser.me/api/portraits/men/1.jpg'
  },
  {
    id: '22',
    phoneNumber: '+55 21 91234-5678',
    name: 'Maria Oliveira',
    lastMessage: 'Enviado o documento que pediu!',
    lastMessageTime: 'Ontem',
    imageUrl: 'https://randomuser.me/api/portraits/women/2.jpg'
  },
  {
    id: '23',
    phoneNumber: '+1 305 555-0198',
    name: 'Carlos Eduardo',
    lastMessage: 'Vamos marcar a reunião para amanhã?',
    lastMessageTime: 'Segunda-feira',
    imageUrl: 'https://randomuser.me/api/portraits/men/3.jpg'
  },
  {
    id: '24',
    phoneNumber: '+33 6 22 33 44 55',
    name: 'Sophie Martin',
    lastMessage: 'Bonjour! Ça va?',
    lastMessageTime: 'Semana passada',
    imageUrl: 'https://randomuser.me/api/portraits/women/4.jpg'
  },
  {
    id: '25',
    phoneNumber: '+49 152 12345678',
    name: 'Lukas Schmidt',
    lastMessage: 'Vielen Dank! Bis später!',
    lastMessageTime: '2 semanas atrás',
    imageUrl: 'https://randomuser.me/api/portraits/men/5.jpg'
  }
];


type Props = {}

const ConversationsList: React.FC = () => {
  const params = useParams();
  const conversationId = params?.conversationId as string | undefined;
  console.log(params);
  return (
    <div className="w-full">
      {mockedConversations.map(conversation => (
        <ConversationItem
          key={conversation.id}
          {...conversation}
          isSelected={conversation.id === conversationId}
        />
      ))}
    </div>
  );
};

export default ConversationsList;