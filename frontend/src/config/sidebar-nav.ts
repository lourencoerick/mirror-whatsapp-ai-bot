import {
    Home,
    Inbox,
    PlusSquare,
    Users,
    UserPlus,
    MessageSquare,
    UserCheck,
    Send,
    Settings,
    Briefcase,
    ShoppingBag,
    FileText,
    BookOpen,
    Activity,
    CreditCard,
    LifeBuoy,
  } from 'lucide-react';
  import type { LucideIcon } from 'lucide-react';
  
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
      href: '/dashboard/seller-setup',
      icon: Settings,
      children: [
        { name: 'Perfil da Empresa', href: '/dashboard/seller-setup/profile', icon: Briefcase },
        { name: 'Catálogo de Produtos', href: '/dashboard/seller-setup/catalog', icon: ShoppingBag },
        { name: 'Templates de Mensagem', href: '/dashboard/seller-setup/templates', icon: FileText },
        { name: 'Base de Conhecimento', href: '/dashboard/seller-setup/documents', icon: BookOpen },
      ],
      hidden: true,
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
  