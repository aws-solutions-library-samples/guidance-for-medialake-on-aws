/**
 * API service for MediaLake Auto-Upgrade System
 */

import { apiClient } from "./apiClient";

export interface Version {
  name: string;
  type: "branch" | "tag";
  sha: string;
  date: string;
  message?: string;
  is_latest?: boolean;
  is_default?: boolean;
}

export interface VersionsResponse {
  branches: Version[];
  tags: Version[];
}

export interface TriggerUpgradeRequest {
  target_version: string;
  version_type: "branch" | "tag";
  confirm_upgrade: boolean;
}

export interface TriggerUpgradeResponse {
  message: string;
  upgrade_id: string;
  target_version: string;
  pipeline_execution_id: string;
  estimated_duration: string;
}

export interface UpgradeProgress {
  stage: string;
  percentage: number;
  current_action: string;
}

export interface ActiveUpgrade {
  upgrade_id: string;
  target_version: string;
  start_time: string;
  pipeline_execution_id: string;
  progress: UpgradeProgress;
}

export interface UpgradeStatusResponse {
  current_version: string;
  upgrade_status: "idle" | "in_progress" | "completed" | "failed";
  last_upgrade?: {
    version: string;
    timestamp: string;
    status: string;
  };
  active_upgrade?: ActiveUpgrade;
}

export interface UpgradeRecord {
  upgrade_id: string;
  from_version: string;
  to_version: string;
  status: "completed" | "failed";
  start_time: string;
  end_time: string;
  duration: number;
  triggered_by: string;
  pipeline_execution_id: string;
  error_message?: string;
}

export interface UpgradeHistoryResponse {
  data: UpgradeRecord[];
  pagination: {
    next_cursor?: string;
    prev_cursor?: string;
    has_next_page: boolean;
    has_prev_page: boolean;
    limit: number;
  } | null;
}

/**
 * Get available versions (branches and tags) from GitHub
 */
export const getVersions = async (): Promise<VersionsResponse> => {
  console.log("📡 getVersions: Making API call...");
  const response = await apiClient.get<{ body: string }>("/updates/versions");
  console.log("📡 getVersions: Raw response:", response);
  console.log("📡 getVersions: response.data:", response.data);

  // Parse the body string to get the actual data
  const parsedBody = JSON.parse(response.data.body);
  console.log("📡 getVersions: Parsed body:", parsedBody);
  console.log("📡 getVersions: parsedBody.data:", parsedBody.data);

  const result = parsedBody.data;
  console.log("📡 getVersions: Returning:", result);
  return result;
};

/**
 * Trigger immediate upgrade to selected version
 */
export const triggerUpgrade = async (
  request: TriggerUpgradeRequest
): Promise<TriggerUpgradeResponse> => {
  const response = await apiClient.post<{ body: string }>("/updates/trigger", request);
  const parsedBody = JSON.parse(response.data.body);
  return parsedBody.data;
};

/**
 * Get current upgrade status
 */
export const getUpgradeStatus = async (): Promise<UpgradeStatusResponse> => {
  const response = await apiClient.get<{ body: string }>("/updates/status");
  const parsedBody = JSON.parse(response.data.body);
  return parsedBody.data;
};

/**
 * Get upgrade history with pagination
 */
export const getUpgradeHistory = async (
  limit: number = 10,
  cursor?: string
): Promise<UpgradeHistoryResponse> => {
  const params = new URLSearchParams();
  params.append("limit", limit.toString());
  if (cursor) {
    params.append("cursor", cursor);
  }

  const response = await apiClient.get<{ body: string }>(`/updates/history?${params.toString()}`);
  const parsedBody = JSON.parse(response.data.body);

  return {
    data: parsedBody.data,
    pagination: parsedBody.pagination,
  };
};

export const updatesService = {
  getVersions,
  triggerUpgrade,
  getUpgradeStatus,
  getUpgradeHistory,
};
