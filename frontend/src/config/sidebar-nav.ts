import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  BookOpen,
  Briefcase,
  CreditCard,
  FileText,
  Home,
  Inbox,
  LifeBuoy,
  MessageSquare,
  PlusSquare,
  Send,
  Settings,
  ShoppingBag,
  UserCheck,
  UserPlus,
  Users,
} from 'lucide-react';
  
  /**
   * Interface for a navigation item in the sidebar.
   */
  export interface NavItem {
    /** The display name of the item. */
    name: string;
    /** The path (URL) the item points to. */
    href: string;
    /** The icon component to be displayed. */
    icon: LucideIcon;
    /** Optional array of child navigation items. */
    children?: NavItem[];
    /** Optional flag for exact URL matching (for active styling). */
    exactMatch?: boolean;
    /** Optional flag to hide the item from the sidebar. */
    hidden?: boolean;
  }
  
  /**
   * Defines the structure and content of the sidebar navigation in Portuguese,
   * ordered logically to follow the user flow.
   */
  export const sidebarNavItems: NavItem[] = [
    {
      name: 'Home',
      href: '/dashboard',
      icon: Home,
      exactMatch: true,
    },
    {
      name: 'Caixas de Entrada',
      href: '/dashboard/inboxes',
      icon: Inbox,
      children: [
        { name: 'Criar Nova Caixa', href: '/dashboard/inboxes/create', icon: PlusSquare, hidden: true  },
      ],
    },
    {
      name: 'Contatos',
      href: '/dashboard/contacts',
      icon: Users,
      children: [
        { name: 'Adicionar Contato', href: '/dashboard/contacts/add', icon: UserPlus, hidden: true },
      ],
    },
    {
      name: 'Conversas',
      href: '/dashboard/conversations',
      icon: MessageSquare,
      children: [
        {
          name: 'Ação Humana Necessária',
          href: '/dashboard/conversations?status=human-action',
          icon: UserCheck,
          hidden: true,
        },
      ],
      
    },
    {
      name: 'Disparos',
      href: '/dashboard/broadcasts',
      icon: Send,
      children: [
        { name: 'Criar Disparo', href: '/dashboard/broadcasts/create', icon: PlusSquare },
      ],
      hidden: true,
    },
    {
      name: 'Meu Vendedor IA',
      href: '/dashboard/settings',
      icon: Settings,
      children: [
        { name: 'Perfil da Empresa', href: '/dashboard/ssettings/profile', icon: Briefcase, hidden: true },
        { name: 'Catálogo de Produtos', href: '/dashboard/settings/catalog', icon: ShoppingBag, hidden: true },
        { name: 'Templates de Mensagem', href: '/dashboard/settings/templates', icon: FileText, hidden: true },
        { name: 'Base de Conhecimento', href: '/dashboard/settings/documents', icon: BookOpen, hidden: true },
      ],
      hidden: false,
    },
    {
      name: 'Desempenho',
      href: '/dashboard/performance',
      icon: Activity,
      hidden: true,
    },
    {
      name: 'Faturamento',
      href: '/dashboard/billing',
      icon: CreditCard,
      hidden: true,
    },
    {
      name: 'Ajuda & FAQ',
      href: '/dashboard/help',
      icon: LifeBuoy,
      hidden: true,
    },
  ];
  