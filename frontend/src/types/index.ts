export interface TripRequestPayload {
  origin_city?: string | null;
  destination: string;
  start_date: string;
  end_date: string;
  travelers: number;
  budget: number;
  preferences: string[];
  pace?: string | null;
  dietary_preferences: string[];
  hotel_level?: string | null;
  special_notes?: string | null;
  browser_price_enabled?: boolean;
  price_observation_urls?: string[];
}

export interface TripEditPayload {
  trip_id: string;
  current_itinerary: Itinerary;
  user_instruction: string;
  edit_scope?: string | null;
  preserve_constraints: string[];
}

export type SourceType =
  | "demo"
  | "estimate"
  | "user_input"
  | "tavily"
  | "official_api"
  | "browser_observed";

export interface SourceRecord {
  title: string;
  url?: string | null;
  summary: string;
  queried_at: string;
  source_type: SourceType;
  category?: string | null;
}

export interface AgentExecutionEvent {
  request_id: string;
  user_id?: number | null;
  trip_id?: string | null;
  agent: string;
  tool?: string | null;
  status: string;
  duration_ms: number;
  retry_count: number;
  fallback: boolean;
  error?: string | null;
  token_usage: Record<string, number>;
  source_type?: SourceType | null;
}

export interface SpotItem {
  name: string;
  start_time?: string | null;
  end_time?: string | null;
  description?: string | null;
  estimated_cost?: number;
  location?: string | null;
  image_url?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  poi_id?: string | null;
  source_type?: SourceType;
  cost_source_type?: SourceType;
}

export interface MealItem {
  name: string;
  meal_type: string;
  estimated_cost?: number;
  notes?: string | null;
  source_type?: SourceType;
  cost_source_type?: SourceType;
}

export interface HotelItem {
  name: string;
  level?: string | null;
  estimated_cost?: number;
  location?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  source_type?: SourceType;
  cost_source_type?: SourceType;
}

export interface TransportItem {
  mode: string;
  from_place?: string | null;
  to_place?: string | null;
  estimated_cost?: number;
  duration?: string | null;
  distance_km?: number | null;
  estimated_minutes?: number | null;
  source_type?: SourceType;
  cost_source_type?: SourceType;
}

export interface DayPlan {
  day_index: number;
  date?: string | null;
  theme?: string | null;
  spots: SpotItem[];
  meals: MealItem[];
  hotel?: HotelItem | null;
  transport: TransportItem[];
  notes: string[];
}

export interface BudgetBreakdown {
  transport: number;
  hotel: number;
  meals: number;
  tickets: number;
  other: number;
  total: number;
  source_type?: SourceType;
}

export interface CandidateItinerary {
  candidate_id: string;
  title: string;
  strategy: string;
  summary: string;
  days: DayPlan[];
  estimated_budget: number;
  budget_breakdown: BudgetBreakdown;
  differences: string[];
}

export interface Itinerary {
  trip_id: string;
  destination: string;
  summary: string;
  days: DayPlan[];
  estimated_budget: number;
  budget_breakdown: BudgetBreakdown;
  tips: string[];
  source_notes: string[];
  source_records?: SourceRecord[];
  execution_events?: AgentExecutionEvent[];
  candidate_itineraries?: CandidateItinerary[];
}

export interface TripVersionSummary {
  trip_id: string;
  version_number: number;
  change_type: string;
  summary: string;
  created_at?: string | null;
}

export interface TripVersionListResponse {
  trip_id: string;
  total: number;
  items: TripVersionSummary[];
}

export interface TripVersionDetailResponse {
  trip_id: string;
  version_number: number;
  change_type: string;
  itinerary: Itinerary;
  created_at?: string | null;
}

export interface TripVersionCompareResponse {
  trip_id: string;
  from_version: number;
  to_version: number;
  differences: string[];
}

export interface TripVersionRestoreResponse {
  trip_id: string;
  restored_from_version: number;
  new_version_number: number;
  itinerary: Itinerary;
}

export interface UserMemoryItem {
  id: number;
  memory_type: string;
  content: string;
  created_at?: string | null;
}

export interface UserMemoryResponse {
  enabled: boolean;
  items: UserMemoryItem[];
}

export interface HumanConfirmationItem {
  id: number;
  trip_id?: string | null;
  confirmation_type: string;
  status: string;
  payload: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface HumanConfirmationListResponse {
  total: number;
  items: HumanConfirmationItem[];
}

export interface TripSaveResponse {
  message: string;
  trip_id: string;
}

export interface TripSummaryItem {
  trip_id: string;
  destination: string;
  summary: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TripListResponse {
  total: number;
  items: TripSummaryItem[];
}

export interface TripDetailResponse {
  trip_id: string;
  itinerary: Itinerary;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WeatherForecastDay {
  date?: string | null;
  week?: string | null;
  day_weather?: string | null;
  night_weather?: string | null;
  day_temp?: string | null;
  night_temp?: string | null;
  day_wind?: string | null;
  night_wind?: string | null;
  source_type?: SourceType;
}

export interface WeatherForecastResponse {
  city: string;
  province?: string | null;
  adcode?: string | null;
  report_time?: string | null;
  days: WeatherForecastDay[];
  source_type?: SourceType;
}

export interface AuthRequestPayload {
  username: string;
  password: string;
}

export interface AuthUser {
  id: number;
  username: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export type AssistantIntent =
  | "modify_trip"
  | "explain_plan"
  | "query_trip"
  | "confirm_action"
  | "cancel_action"
  | "general_travel_question"
  | "unsupported";

export type ConversationRole = "user" | "assistant" | "system";

export type ConversationMessageType =
  | "text"
  | "trip_update"
  | "explanation"
  | "confirmation"
  | "error";

export interface AssistantMessagePayload {
  trip_id: string;
  message: string;
  candidate_id?: string | null;
  confirmation_id?: number | null;
  action?: "confirmed" | "rejected" | null;
}

export interface ConversationMessageItem {
  id: string;
  conversation_id: string;
  role: ConversationRole;
  message_type: ConversationMessageType;
  content: string;
  structured_payload: Record<string, unknown>;
  created_at?: string | null;
  optimistic?: boolean;
}

export interface AssistantMessageResponse {
  conversation_id: string;
  message_id: string;
  reply: string;
  intent: AssistantIntent;
  trip_changed: boolean;
  new_version_number?: number | null;
  confirmation_required: boolean;
  execution_events: AgentExecutionEvent[];
  itinerary?: Itinerary | null;
  message?: ConversationMessageItem | null;
  source_records: SourceRecord[];
}

export interface ConversationMessagesResponse {
  conversation_id?: string | null;
  trip_id: string;
  total: number;
  items: ConversationMessageItem[];
}

export interface ConversationClearResponse {
  trip_id: string;
  deleted_count: number;
}

export interface BrowserNavigatePayload {
  category: "flight" | "train" | "hotel" | "vacation";
  origin_city?: string;
  destination?: string;
  start_date?: string;
  end_date?: string;
}

export interface BrowserNavigateResponse {
  status: string;
  url: string | null;
  message: string;
}
