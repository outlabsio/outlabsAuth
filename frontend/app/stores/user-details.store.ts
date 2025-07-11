// ~/stores/user-details.store.ts

// Define User interface matching the backend model and frontend usage
// (Consider moving to a central types file later)
interface User {
  id: string;
  email: string;
  name: string; // Adjusted to required based on previous component needs
  permissions: string[];
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  is_team_member: boolean;
  created_at: string;
  locale: string;
  last_login: string; // Adjusted to required based on previous component needs
  account?: UserAccount; // Added account property
  // Optional fields from backend model, add if needed
  hashed_password?: string;
  password_reset_token?: string | null;
  password_reset_token_expires_at?: string | null;
  pending_email?: string | null;
  email_change_token?: string | null;
  email_change_token_expires_at?: string | null;
  updated_at?: string | null;
}

// Interface for User Account data
interface UserAccount {
  token_balance: number;
  is_active: boolean;
  auto_topup: {
    enabled: boolean;
    threshold: number;
    pack_type: string | null;
  };
  payment_methods: PaymentMethod[];
  default_payment_method: string | null;
  total_tokens_used: number;
  total_purchases: number;
  last_purchase: string | null;
  has_available_tokens: boolean;
  has_payment_method: boolean;
  is_eligible_for_auto_topup: boolean;
  needs_topup: boolean;
}

// Interface for Payment Method
interface PaymentMethod {
  id: string;
  last4: string;
  exp_month: number;
  exp_year: number;
  brand: string;
  is_default: boolean;
  customer_id: string;
}

// Interface for PaymentEvent (copied from transactions.vue)
// Consider moving to a central types file
enum PaymentEventType {
  PAYMENT_SUCCEEDED = "payment.succeeded",
  PAYMENT_FAILED = "payment.failed",
  PAYMENT_RETRIED = "payment.retried",
  PAYMENT_REFUNDED = "payment.refunded",
  PAYMENT_METHOD_UPDATED = "payment_method.updated",
  AUTO_TOPUP_ENABLED = "auto_topup.enabled",
  AUTO_TOPUP_DISABLED = "auto_topup.disabled",
  AUTO_TOPUP_TRIGGERED = "auto_topup.triggered",
  AUTO_TOPUP_FAILED = "auto_topup.failed",
  AUTO_TOPUP_SETTINGS_UPDATED = "auto_topup.settings_updated",
  AUTO_TOPUP_RESTRICTED = "auto_topup.restricted",
  AUTO_TOPUP_RESTRICTION_LIFTED = "auto_topup.restriction_lifted",
  ELIGIBLE_FOR_AUTO_TOPUP = "user.eligible_for_auto_topup",
}
interface PaymentEvent {
  id: string;
  account?: string;
  user?: string;
  event_type: PaymentEventType;
  timestamp: string;
  amount?: number | null;
  currency?: string | null;
  provider?: string | null;
  payment_method_id?: string | null;
  topup_threshold?: number | null;
  topup_amount?: number | null;
  error_message?: string | null;
  details?: Record<string, any> | null;
}

// Enums and Interface based on token_event_model.py
// EXPORT these so they can be imported by components
export enum TokenOperationType {
  PURCHASE = "token.purchase",
  PROMO = "token.promo",
  ADMIN_GRANT = "token.admin_grant",
  REFUND = "token.refund",
  REWARD = "token.reward",
  COMPENSATION = "token.compensation",
  READING_ADVANCED = "debit.reading.advanced",
  READING_ORACLE = "debit.reading.oracle",
  EXPIRED = "debit.expired",
  ADMIN_DEDUCT = "debit.admin_deduct",
  LOW_BALANCE = "system.low_balance",
  BALANCE_ADJUSTED = "system.adjusted",
}

export enum TokenEventCategory {
  PURCHASE = "purchase",
  REWARD = "reward",
  ADMIN = "admin",
  READING = "reading",
  SYSTEM = "system",
  PROMO = "promotional",
}

export enum TokenEventSource {
  PAYMENT = "payment",
  ACHIEVEMENT = "achievement",
  ADMIN = "admin",
  SYSTEM = "system",
  PROMO_CODE = "promo_code",
  REFERRAL = "referral",
  AUTO_TOPUP = "auto_topup",
  COMPENSATION = "compensation",
  MILESTONE = "milestone",
}

export interface TokenEvent {
  id: string; // Assuming beanie assigns an ID
  account?: string; // Link mapped to string ID or object
  user?: string; // Link mapped to string ID or object
  operation_type: TokenOperationType;
  category: TokenEventCategory;
  timestamp: string; // datetime mapped to ISO string
  token_amount: number;
  balance_after: number;
  description?: string | null;
  product_id?: string | null;
  product_cost?: number | null;
  source?: TokenEventSource | null;
  payment_intent_id?: string | null;
  provider_transaction_id?: string | null;
  provider?: string | null;
  admin_user?: string | null; // Link mapped to string ID or object
  reason?: string | null;
  details?: Record<string, any> | null;
}

// API response interface (different field names from internal TokenEvent)
interface ApiTokenEvent {
  id: string;
  user_id: string;
  account_id: string;
  operation_type: string;
  category: string;
  timestamp: string;
  token_amount: number;
  balance_after: number;
  description?: string;
  product_id?: string;
  product_cost?: number;
  source?: string;
  payment_intent_id?: string;
  provider_transaction_id?: string;
  provider?: string;
  admin_user_id?: string;
  reason?: string;
  details?: Record<string, any>;
}

interface TokenEventsResponse {
  events: ApiTokenEvent[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
}

// Define interfaces for token grants
interface TokenGrantRequest {
  target_user_id: string;
  token_amount: number;
  reason: string;
  description?: string;
  category?: string;
  source?: string;
  details?: Record<string, any>;
}

interface TokenGrantResponse extends ApiTokenEvent {}

// Interface for User Account Statistics
interface UserAccountStats {
  token_balance: number;
  total_token_usage: number;
  total_readings: number;
  basic_readings: number;
  advanced_readings: number;
  oracle_readings: number;
  last_activity_timestamp?: string | null;
}

export const useUserDetailsStore = defineStore("userDetails", () => {
  const user = ref<User | null>(null);
  const loading = ref(false);
  const error = ref<any | null>(null); // Store potential errors

  // User Transactions State
  const userTransactions = ref<PaymentEvent[]>([]);
  const transactionsLoading = ref(false);
  const transactionsError = ref<any | null>(null);

  // User Token Events State
  const userTokenEvents = ref<TokenEvent[]>([]);
  const tokenEventsLoading = ref(false);
  const tokenEventsError = ref<any | null>(null);

  // Token Grants State
  const tokenGrants = ref<TokenEvent[]>([]);
  const grantsLoading = ref(false);
  const grantsError = ref<any | null>(null);
  const grantingTokens = ref(false);

  // User Account Stats State
  const accountStats = ref<UserAccountStats | null>(null);
  const statsLoading = ref(false);
  const statsError = ref<any | null>(null);

  const authStore = useAuthStore(); // Get instance of auth store

  // Action to fetch user details
  async function fetchUserDetails(userId: string) {
    if (!userId) {
      console.error("fetchUserDetails: userId is required");
      error.value = new Error("User ID is required");
      user.value = null;
      return;
    }

    loading.value = true;
    error.value = null;
    console.log(`Fetching details for user ID: ${userId}`);

    try {
      // Use apiCall from authStore to fetch user details
      const fetchedUser = await authStore.apiCall<User>(`/users/${userId}`); // Use the new endpoint

      // Ensure critical fields are present or defaulted
      // (Adjust defaults as needed based on actual API response possibility)
      user.value = {
        ...fetchedUser,
        name: fetchedUser.name || `User ${fetchedUser.id}`, // Default name if null/undefined
        last_login: fetchedUser.last_login || new Date(0).toISOString(), // Default last_login if null/undefined
        permissions: fetchedUser.permissions || [], // Default permissions if null/undefined
      };
      console.log("User details fetched:", user.value);
    } catch (err: any) {
      console.error("Error fetching user details:", err);
      error.value = err;
      user.value = null;
      // Consider using useToast() for user feedback if desired
      // const toast = useToast();
      // toast.add({ title: 'Error', description: err.data?.detail || err.message || 'Could not load user details.', color: 'error' });
    } finally {
      loading.value = false;
    }
  }

  // Action to fetch user transactions
  async function fetchUserTransactions(userId: string) {
    if (!userId) {
      console.error("fetchUserTransactions: userId is required");
      transactionsError.value = new Error("User ID is required");
      userTransactions.value = [];
      return;
    }

    transactionsLoading.value = true;
    transactionsError.value = null; // Clear previous errors
    console.log(`Fetching transactions for user ID: ${userId}`);

    try {
      // --- Replace with actual API call ---
      await new Promise((resolve) => setTimeout(resolve, 900)); // Simulate delay

      // Mock data generation (copied from transactions.vue)
      const eventTypes: PaymentEventType[] = [
        PaymentEventType.PAYMENT_SUCCEEDED,
        PaymentEventType.PAYMENT_FAILED,
        PaymentEventType.PAYMENT_REFUNDED,
        PaymentEventType.PAYMENT_METHOD_UPDATED,
        PaymentEventType.AUTO_TOPUP_ENABLED,
        PaymentEventType.AUTO_TOPUP_DISABLED,
        PaymentEventType.AUTO_TOPUP_TRIGGERED,
        PaymentEventType.AUTO_TOPUP_FAILED,
        PaymentEventType.AUTO_TOPUP_SETTINGS_UPDATED,
        PaymentEventType.AUTO_TOPUP_RESTRICTED,
        PaymentEventType.AUTO_TOPUP_RESTRICTION_LIFTED,
        PaymentEventType.ELIGIBLE_FOR_AUTO_TOPUP,
      ];
      const mockTransactions: PaymentEvent[] = Array.from({ length: Math.floor(Math.random() * 20) + 5 }, (_, i) => {
        const eventType = eventTypes[Math.floor(Math.random() * eventTypes.length)] ?? PaymentEventType.PAYMENT_SUCCEEDED;
        const hasAmount = [
          PaymentEventType.PAYMENT_SUCCEEDED,
          PaymentEventType.PAYMENT_FAILED,
          PaymentEventType.PAYMENT_REFUNDED,
          PaymentEventType.AUTO_TOPUP_TRIGGERED,
          PaymentEventType.AUTO_TOPUP_FAILED,
        ].includes(eventType);
        const isError = [PaymentEventType.PAYMENT_FAILED, PaymentEventType.AUTO_TOPUP_FAILED, PaymentEventType.AUTO_TOPUP_RESTRICTED].includes(eventType);
        return {
          id: `evt-${userId}-${i}`,
          user: userId,
          event_type: eventType,
          timestamp: new Date(Date.now() - Math.random() * 1000 * 60 * 60 * 24 * 180).toISOString(),
          amount: hasAmount ? Math.random() * 50 + 5 : null,
          currency: hasAmount ? ["USD", "EUR"][Math.floor(Math.random() * 2)] : null,
          provider: [PaymentEventType.PAYMENT_SUCCEEDED, PaymentEventType.PAYMENT_FAILED, PaymentEventType.PAYMENT_REFUNDED].includes(eventType) ? "stripe" : null,
          error_message: isError ? `Simulated error: ${eventType}` : null,
          details: { info: `Mock detail ${i}` },
        };
      }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      // --- End Mock ---

      userTransactions.value = mockTransactions; // Update state
    } catch (err: any) {
      console.error("Error fetching transactions:", err);
      transactionsError.value = err;
      userTransactions.value = [];
    } finally {
      transactionsLoading.value = false;
    }
  }

  // Action to fetch user token events
  async function fetchUserTokenEvents(userId: string) {
    if (!userId) {
      console.error("fetchUserTokenEvents: userId is required");
      tokenEventsError.value = new Error("User ID is required");
      userTokenEvents.value = [];
      return;
    }

    tokenEventsLoading.value = true;
    tokenEventsError.value = null;
    console.log(`Fetching token events for user ID: ${userId}`);

    try {
      // --- Replace with actual API call ---
      await new Promise((resolve) => setTimeout(resolve, 750)); // Simulate delay

      // Mock data generation
      const operationTypes = Object.values(TokenOperationType);
      const categories = Object.values(TokenEventCategory);
      const sources = Object.values(TokenEventSource);
      let currentBalance = Math.floor(Math.random() * 500) + 1000; // Start with a random balance

      const mockTokenEvents: TokenEvent[] = Array.from({ length: Math.floor(Math.random() * 30) + 10 }, (_, i) => {
        const operationType = operationTypes[Math.floor(Math.random() * operationTypes.length)] ?? TokenOperationType.BALANCE_ADJUSTED;
        const category = categories[Math.floor(Math.random() * categories.length)] ?? TokenEventCategory.SYSTEM;
        const source = sources[Math.floor(Math.random() * sources.length)] ?? TokenEventSource.SYSTEM;
        let tokenAmount = 0;

        // Determine amount based on operation type
        if (operationType.startsWith("token.")) {
          // Positive amounts
          tokenAmount = Math.floor(Math.random() * 100) + 10;
        } else if (operationType.startsWith("debit.")) {
          // Negative amounts
          tokenAmount = -(Math.floor(Math.random() * 20) + 1);
        } // System events have 0 amount

        currentBalance += tokenAmount;

        return {
          id: `tev-${userId}-${i}`,
          user: userId,
          operation_type: operationType,
          category: category,
          timestamp: new Date(Date.now() - Math.random() * 1000 * 60 * 60 * 24 * 120).toISOString(), // Within last 120 days
          token_amount: tokenAmount,
          balance_after: currentBalance,
          source: source,
          description: `Mock event ${i} for ${operationType}`,
          // Add other optional fields randomly if needed
        };
      }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      // --- End Mock ---

      userTokenEvents.value = mockTokenEvents; // Update state
    } catch (err: any) {
      console.error("Error fetching token events:", err);
      tokenEventsError.value = err;
      userTokenEvents.value = [];
    } finally {
      tokenEventsLoading.value = false;
    }
  }

  // Action to grant tokens to a user
  async function grantTokensToUser(grantData: TokenGrantRequest): Promise<TokenGrantResponse | null> {
    if (!grantData.target_user_id || !grantData.token_amount || !grantData.reason) {
      console.error("grantTokensToUser: target_user_id, token_amount, and reason are required");
      grantsError.value = new Error("Missing required fields for token grant");
      return null;
    }

    grantingTokens.value = true;
    grantsError.value = null;
    console.log(`Granting ${grantData.token_amount} tokens to user ${grantData.target_user_id}`);

    try {
      const response = await authStore.apiCall<TokenGrantResponse>("/admin/grant-tokens", {
        method: "POST",
        body: {
          target_user_id: grantData.target_user_id,
          token_amount: grantData.token_amount,
          reason: grantData.reason,
          description: grantData.description || `Admin granted ${grantData.token_amount} tokens`,
          category: grantData.category || "admin",
          source: grantData.source || "admin",
          details: grantData.details || {},
        },
      });

      console.log("Token grant successful:", response);

      // Add the new grant to the grants list if it's for the current user
      if (grantData.target_user_id === user.value?.id) {
        const mappedEvent: TokenEvent = {
          ...response,
          user: response.user_id,
          account: response.account_id,
          admin_user: response.admin_user_id,
          operation_type: response.operation_type as TokenOperationType,
          category: response.category as TokenEventCategory,
          source: response.source as TokenEventSource,
        };
        tokenGrants.value.unshift(mappedEvent);
      }

      return response;
    } catch (err: any) {
      console.error("Error granting tokens:", err);
      grantsError.value = err;
      throw err;
    } finally {
      grantingTokens.value = false;
    }
  }

  // Action to fetch admin grants for a user
  async function fetchUserTokenGrants(userId: string) {
    if (!userId) {
      console.error("fetchUserTokenGrants: userId is required");
      grantsError.value = new Error("User ID is required");
      tokenGrants.value = [];
      return;
    }

    grantsLoading.value = true;
    grantsError.value = null;
    console.log(`Fetching token grants for user ID: ${userId}`);

    try {
      // Use the admin token activities endpoint which filters for admin activities only
      const response = await authStore.apiCall<TokenEventsResponse>(`/admin/token-activities`, {
        params: {
          user_id: userId, // Filter by the user who received the grants
          operation_type: "token.admin_grant", // Only admin grants
          size: 100, // Get more grants to show history
        },
      });

      tokenGrants.value = response.events.map(
        (event): TokenEvent => ({
          ...event,
          user: event.user_id,
          account: event.account_id,
          admin_user: event.admin_user_id,
          operation_type: event.operation_type as TokenOperationType,
          category: event.category as TokenEventCategory,
          source: event.source as TokenEventSource,
        })
      );
      console.log(`Fetched ${tokenGrants.value.length} token grants for user ${userId}`);
    } catch (err: any) {
      console.error("Error fetching token grants:", err);
      grantsError.value = err;
      tokenGrants.value = [];
    } finally {
      grantsLoading.value = false;
    }
  }

  // Action to fetch user account statistics
  async function fetchUserAccountStats(userId: string) {
    if (!userId) {
      console.error("fetchUserAccountStats: userId is required");
      statsError.value = new Error("User ID is required");
      accountStats.value = null;
      return;
    }

    statsLoading.value = true;
    statsError.value = null;
    console.log(`Fetching account statistics for user ID: ${userId}`);

    try {
      const response = await authStore.apiCall<UserAccountStats>(`/users/${userId}/stats`);
      accountStats.value = response;
      console.log(`Fetched account statistics for user ${userId}:`, response);
    } catch (err: any) {
      console.error("Error fetching user account statistics:", err);
      statsError.value = err;
      accountStats.value = null;
    } finally {
      statsLoading.value = false;
    }
  }

  return {
    user,
    loading,
    error,
    fetchUserDetails,
    // Expose transaction state and action
    userTransactions,
    transactionsLoading,
    transactionsError,
    fetchUserTransactions,
    // Expose token event state and action
    userTokenEvents,
    tokenEventsLoading,
    tokenEventsError,
    fetchUserTokenEvents,
    // Expose token grants state and actions
    tokenGrants,
    grantsLoading,
    grantsError,
    grantingTokens,
    grantTokensToUser,
    fetchUserTokenGrants,
    // Expose user account stats state and action
    accountStats,
    statsLoading,
    statsError,
    fetchUserAccountStats,
  };
});
