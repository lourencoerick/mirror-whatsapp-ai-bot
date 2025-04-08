export interface Contact {
    id: string;
    name: string;
    phone_number: string;
    email: string;
}


export interface PaginatedContact {
    items: Contact[];
    page: number;
    total: number;
    per_page: number;
  }