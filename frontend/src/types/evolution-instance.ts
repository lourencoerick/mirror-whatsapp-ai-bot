/**
 * Represents the possible connection statuses for an Evolution API instance.
 * Should ideally match the EvolutionInstanceStatus Enum in the backend.
 */
export type EvolutionInstanceStatus =
  | "CONNECTED"
  | "DISCONNECTED"
  | "QRCODE"
  | "API_ERROR"
  | "CONFIG_ERROR"
  | "UNKNOWN"
  | string; 

/**
 * Represents the structure of an Evolution API Instance record from the backend.
 * Matches the EvolutionInstanceRead Pydantic schema.
 */
export interface EvolutionInstance {
  id: string; 
  account_id: string;
  instance_name: string; 
  shared_api_url: string;
  status: EvolutionInstanceStatus;
  created_at: string; 
  updated_at: string; 
}