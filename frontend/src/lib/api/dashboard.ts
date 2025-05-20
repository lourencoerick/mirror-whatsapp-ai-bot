/* eslint-disable @typescript-eslint/no-unused-vars */
// src/lib/api/dashboard.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch"; // Adjust path as needed
import { components } from "@/types/api"; // Assuming types are generated here

// Type aliases for the specific response schemas we'll be using
type DashboardStatsResponse = components["schemas"]["DashboardStatsResponse"];
type DashboardMessageVolumeResponse =
  components["schemas"]["DashboardMessageVolumeResponse"];

// API prefix for dashboard endpoints
const DASHBOARD_API_PREFIX = "/api/v1/dashboard"; // Matches the prefix in your FastAPI router

/**
 * Fetches aggregated dashboard statistics (KPIs, conversation counts, message counts).
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {string} startDate - The start date for the period (YYYY-MM-DD).
 * @param {string} endDate - The end date for the period (YYYY-MM-DD).
 * @param {string} [inboxId] - Optional UUID of an inbox to filter statistics by.
 * @returns {Promise<DashboardStatsResponse>} A promise that resolves with the dashboard statistics.
 * @throws {Error} If the API call fails or returns a non-OK status.
 */
export const getDashboardStats = async (
  fetcher: FetchFunction,
  startDate: string,
  endDate: string,
  inboxId?: string
): Promise<DashboardStatsResponse> => {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  if (inboxId) {
    params.append("inbox_id", inboxId);
  }

  const endpoint = `${DASHBOARD_API_PREFIX}/stats?${params.toString()}`;
  console.log(`[API Client] Fetching dashboard stats from: ${endpoint}`); // Optional logging

  try {
    const response = await fetcher(endpoint, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Ignore if response body is not JSON
      }
      throw new Error(`Failed to fetch dashboard statistics: ${errorDetail}`);
    }

    const data: DashboardStatsResponse = await response.json();
    console.log("[API Client] Successfully fetched dashboard stats:", data); // Optional logging
    return data;
  } catch (error) {
    console.error("[API Client] Error in getDashboardStats:", error);
    // Re-throw the error pobreza to be handled by react-query or other callers
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(
      "An unknown error occurred while fetching dashboard statistics."
    );
  }
};

/**
 * Fetches time series data for message volume.
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {string} startDate - The start date for the period (YYYY-MM-DD).
 * @param {string} endDate - The end date for the period (YYYY-MM-DD).
 * @param {"day" | "hour"} granularity - The granularity of the time series ('day' or 'hour').
 * @param {string} [inboxId] - Optional UUID of an inbox to filter message volume by.
 * @returns {Promise<DashboardMessageVolumeResponse>} A promise that resolves with the message volume data.
 * @throws {Error} If the API call fails or returns a non-OK status.
 */
export const getDashboardMessageVolume = async (
  fetcher: FetchFunction,
  startDate: string,
  endDate: string,
  granularity: "day" | "hour",
  inboxId?: string
): Promise<DashboardMessageVolumeResponse> => {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    granularity: granularity,
  });
  if (inboxId) {
    params.append("inbox_id", inboxId);
  }

  const endpoint = `${DASHBOARD_API_PREFIX}/message-volume?${params.toString()}`;
  console.log(`[API Client] Fetching message volume from: ${endpoint}`); // Optional logging

  try {
    const response = await fetcher(endpoint, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Ignore if response body is not JSON
      }
      throw new Error(`Failed to fetch message volume: ${errorDetail}`);
    }

    const data: DashboardMessageVolumeResponse = await response.json();
    console.log("[API Client] Successfully fetched message volume:", data); // Optional logging
    return data;
  } catch (error) {
    console.error("[API Client] Error in getDashboardMessageVolume:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("An unknown error occurred while fetching message volume.");
  }
};
