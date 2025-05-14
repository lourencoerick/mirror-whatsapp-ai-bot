import { components } from "@/types/api";

type EvolutionInstanceStatus = components["schemas"]["EvolutionInstanceStatus"];

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
