// src/lib/enums.ts
import { components } from "@/types/api";

export const AppBetaStatusEnum = {
  PENDING_APPROVAL: "pending_approval",
  APPROVED: "approved",
  DENIED: "denied",
  INVITED: "invited",
} as const;

export type AppBetaStatusEnumType =
  (typeof AppBetaStatusEnum)[keyof typeof AppBetaStatusEnum];

export type BetaTesterStatusResponse =
  components["schemas"]["BetaTesterStatusResponse"];
