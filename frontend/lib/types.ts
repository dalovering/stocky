// Mirrors the backend schemas (app/schemas). Keep in sync when the API changes.

export type Condition = "New" | "Used" | "Lost" | "Damaged" | "Discarded";

export type ItemStatus = "Available" | "On loan" | "Damaged" | "Lost" | "Discarded";

export type EventType =
  | "create"
  | "checkout"
  | "checkin"
  | "damage_report"
  | "loss_report"
  | "discard"
  | "repair";

export interface Group {
  id: string;
  name: string;
  parent_id: string | null;
  permissions: Record<string, unknown>;
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
  barcode: string;
  item_type_name: string | null;
  status: ItemStatus;
  holder_user_id: string | null;
  holder_name: string | null;
  checked_out_at: string | null;
}

export interface ItemEvent {
  id: string;
  item_id: string;
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
export type ScanAction =
  | "login"
  | "checked_out"
  | "checked_in"
  | "open_modal"
  | "unknown";

export interface ScanResponse {
  kind: ScanKind;
  action: ScanAction;
  message: string;
  user: UserDetail | null;
  item: Item | null;
}
