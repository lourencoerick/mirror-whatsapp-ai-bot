/* eslint-disable @typescript-eslint/no-explicit-any */

export interface ContactImportSummary {
    total_rows_processed: number;
    successful_imports: number;
    failed_imports: number;
    errors: Array<{
      
      row_number: number;
      reason: string;
      data: Record<string, any>; 
    }>;
  }
  

  
export interface ContactImportJobStatusResponse {
    id: string; 
    status: "PENDING" | "PROCESSING" | "COMPLETE" | "FAILED";
    file_key?: string | null; 
    created_at: string; 
    finished_at?: string | null; 
    result_summary?: ContactImportSummary | null; 
  }


export interface ImportJobListItem {
    id: string; 
    status: string; 
    original_filename?: string | null;
    created_at: string; 
    finished_at?: string | null; 
  }
  
  export interface PaginatedImportJobListResponse {
    total_items: number;
    total_pages: number;
    page: number;
    size: number;
    items: ImportJobListItem[];
  }


export interface ImportJobStartResponse {
  id: string; 
  status: string;
}


