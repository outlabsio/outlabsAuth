import type { Period, Range } from "~/types";

export interface StatsDataPoint {
  timestamp: string;
  count: number;
}

export interface AnonymousReadingsStatsResponse {
  query_parameters: {
    period: string;
    start_date?: string;
    end_date?: string;
    interval: string;
  };
  total_anonymous_readings_in_period: number;
  data_points: StatsDataPoint[];
}

export interface RegisteredReadingsStatsResponse {
  query_parameters: {
    period: string;
    start_date?: string;
    end_date?: string;
    interval: string;
  };
  total_registered_readings_in_period: number;
  data_points: StatsDataPoint[];
}

export interface UserRegistrationStatsResponse {
  query_parameters: {
    period: string;
    start_date?: string;
    end_date?: string;
    interval: string;
  };
  data_points: Array<{
    timestamp: string;
    registrations_in_interval: number;
    cumulative_total_users_at_interval_end: number;
  }>;
  current_total_users: number;
}

export interface UserSummaryStatsResponse {
  total_users: number;
  daily_active_users: number;
  weekly_active_users: number;
  monthly_active_users: number;
  last_calculated_at: string;
}

export interface ActiveUserStatsResponse {
  period_type: string;
  active_users_count: number;
  start_date_active_period: string;
  end_date_active_period: string;
}

export const useStatsStore = defineStore("stats", () => {
  const authStore = useAuthStore();

  // Helper function to convert Period to API period
  const convertPeriodToApiPeriod = (period: Period, range: Range): string => {
    const diffInDays = Math.ceil((range.end.getTime() - range.start.getTime()) / (1000 * 60 * 60 * 24));

    if (diffInDays <= 1) {
      return "last_24_hours";
    } else {
      return "custom";
    }
  };

  // Helper function to get interval based on period
  const getInterval = (period: Period): string => {
    switch (period) {
      case "daily":
        return "hourly";
      case "weekly":
        return "daily";
      case "monthly":
        return "daily";
      default:
        return "daily";
    }
  };

  // Anonymous readings stats
  const getAnonymousReadingsStats = async (period: Period, range: Range): Promise<AnonymousReadingsStatsResponse> => {
    const apiPeriod = convertPeriodToApiPeriod(period, range);
    const interval = getInterval(period);

    const params = new URLSearchParams({
      period: apiPeriod,
      interval,
    });

    if (apiPeriod === "custom") {
      params.append("start_date", range.start.toISOString());
      params.append("end_date", range.end.toISOString());
    }

    return await authStore.apiCall<AnonymousReadingsStatsResponse>(`/stats/readings/anonymous?${params.toString()}`);
  };

  // Registered readings stats
  const getRegisteredReadingsStats = async (period: Period, range: Range): Promise<RegisteredReadingsStatsResponse> => {
    const apiPeriod = convertPeriodToApiPeriod(period, range);
    const interval = getInterval(period);

    const params = new URLSearchParams({
      period: apiPeriod,
      interval,
    });

    if (apiPeriod === "custom") {
      params.append("start_date", range.start.toISOString());
      params.append("end_date", range.end.toISOString());
    }

    return await authStore.apiCall<RegisteredReadingsStatsResponse>(`/stats/readings/registered?${params.toString()}`);
  };

  // User registration stats
  const getUserRegistrationStats = async (period: Period, range: Range): Promise<UserRegistrationStatsResponse> => {
    const apiPeriod = convertPeriodToApiPeriod(period, range);
    const interval = getInterval(period);

    const params = new URLSearchParams({
      period: apiPeriod,
      interval,
    });

    if (apiPeriod === "custom") {
      params.append("start_date", range.start.toISOString());
      params.append("end_date", range.end.toISOString());
    }

    return await authStore.apiCall<UserRegistrationStatsResponse>(`/stats/users/registrations?${params.toString()}`);
  };

  // User activity summary
  const getUserActivitySummary = async (): Promise<UserSummaryStatsResponse> => {
    return await authStore.apiCall<UserSummaryStatsResponse>("/stats/users/activity/summary");
  };

  // Active users by period
  const getActiveUsersByPeriod = async (periodType: "daily" | "weekly" | "monthly"): Promise<ActiveUserStatsResponse> => {
    return await authStore.apiCall<ActiveUserStatsResponse>(`/stats/users/activity/${periodType}`);
  };

  return {
    getAnonymousReadingsStats,
    getRegisteredReadingsStats,
    getUserRegistrationStats,
    getUserActivitySummary,
    getActiveUsersByPeriod,
  };
});
