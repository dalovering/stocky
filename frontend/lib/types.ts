// Mirrors the backend schemas (app/schemas). Keep in sync when the API changes.

export type Condition = "On order" | "New" | "Good" | "Fair" | "Worn" | "Damaged";

export type ItemStatus = "Checked out" | "Available" | "Unavailable" | "Lost" | "Discarded";

export type UserStatus = "Active" | "Inactive";

export type EventType =
  | "create"
  | "checkout"
  | "checkin"
  | "damage_report"
  | "loss_report"
  | "discard"
  | "repair"
  | "mark_unavailable"
  | "restore"
  | "attendance";

export const CONDITIONS: Condition[] = ["On order", "New", "Good", "Fair", "Worn", "Damaged"];

export const ITEM_STATUSES: ItemStatus[] = [
  "Checked out",
  "Available",
  "Unavailable",
  "Lost",
  "Discarded",
];

// The statuses shown by default on the admin items table — the "live" ones (hides Lost/Discarded).
export const ACTIVE_ITEM_STATUSES: ItemStatus[] = ["Checked out", "Available", "Unavailable"];

export const USER_STATUSES: UserStatus[] = ["Active", "Inactive"];

// Statuses an admin can set directly (Checked out is loan-driven, not settable).
export const SETTABLE_STATUSES: ItemStatus[] = ["Available", "Unavailable", "Lost", "Discarded"];

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AppSettings {
  kiosk_block_inactive_users: boolean;
  kiosk_idle_timeout_seconds: number;
  admin_idle_timeout_minutes: number;
  timezone: string;
}

/** The kiosk-safe settings subset served by the public /api/kiosk/config endpoint. */
export interface KioskConfig {
  idle_timeout_seconds: number;
}

export interface AuthStatus {
  authenticated: boolean;
  needs_setup: boolean;
}

export interface ImportResult {
  created: number;
  updated: number;
  deleted: number;
  skipped: number;
  errors: { row: number; message: string }[];
}

export interface Group {
  id: string;
  name: string;
  parent_id: string | null;
  permissions: Record<string, unknown>;
  semester_start: string | null;
}

export type Timeframe = "today" | "week" | "semester";

export interface AttendanceUserRow {
  user_id: string;
  name: string;
  barcode: string;
  present: string[]; // ISO dates, subset of the group's scheduled days
  present_count: number;
  absent_count: number;
}

export interface AttendanceGroup {
  group_id: string | null; // null = the "No group" bucket
  group_name: string;
  semester_start: string | null;
  days: string[]; // scheduled days, ascending
  users: AttendanceUserRow[];
  children: AttendanceGroup[];
}

export interface AttendanceReport {
  timeframe: Timeframe;
  timezone: string;
  groups: AttendanceGroup[];
}

export interface GroupTree extends Group {
  children: GroupTree[];
  user_count: number;
}

export interface UserRead {
  id: string;
  name: string;
  group_id: string | null;
  group_name: string | null;
  status: UserStatus;
  barcode: string;
  loan_count: number;
}

export interface UserDetail extends UserRead {
  current_loans: Item[];
}

export interface ItemType {
  id: string;
  name: string;
  manufacturer: string | null;
  author: string | null;
  publish_date: string | null;
  description: string | null;
  photo_url: string | null;
  url: string | null;
  cost: string | null;
  upc_isbn: string | null;
  item_count: number;
}

export interface Item {
  id: string;
  item_type_id: string;
  name: string;
  photo_url: string | null;
  description: string | null;
  purchase_price: string | null;
  purchase_date: string | null;
  location: string | null;
  condition: Condition;
  needs_review: boolean;
  barcode: string;
  item_type_name: string | null;
  status: ItemStatus;
  holder_user_id: string | null;
  holder_name: string | null;
  checked_out_at: string | null;
}

export interface ItemEvent {
  id: string;
  // Null for user-only events (attendance).
  item_id: string | null;
  item_name: string | null;
  user_id: string | null;
  user_name: string | null;
  event_type: EventType;
  note: string | null;
  created_at: string;
}

export interface InventorySummaryRow {
  item_type_id: string;
  item_type_name: string;
  location: string | null;
  total: number;
  available: number;
  on_loan: number;
}

export type ScanKind = "user" | "item" | "unknown";
export type ScanAction = "login" | "checked_out" | "checked_in" | "open_modal" | "unknown";

export interface ScanResponse {
  kind: ScanKind;
  action: ScanAction;
  message: string;
  user: UserDetail | null;
  item: Item | null;
}
