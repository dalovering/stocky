// Typed client for the Stocky API. Cookies (the admin session) are sent with every
// request via `credentials: "include"`.

import type {
  AppSettings,
  Condition,
  Group,
  GroupTree,
  ImportResult,
  InventorySummaryRow,
  Item,
  ItemEvent,
  ItemStatus,
  ItemType,
  Page,
  ScanResponse,
  UserDetail,
  UserRead,
  UserStatus,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}

async function requestBlobPost(path: string, body: unknown): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return res.blob();
}

// Multipart upload (e.g. xlsx import): don't set Content-Type — the browser adds the boundary.
async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/** Trigger a browser download of a fetched blob with the given filename. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const get = <T>(p: string) => request<T>(p);
const post = <T>(p: string, body?: unknown) =>
  request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const patch = <T>(p: string, body: unknown) =>
  request<T>(p, { method: "PATCH", body: JSON.stringify(body) });
const del = (p: string) => request<void>(p, { method: "DELETE" });

export const api = {
  base: BASE,

  // ---- Auth ----
  login: (password: string) => post<{ authenticated: boolean }>("/api/auth/login", { password }),
  logout: () => post<{ authenticated: boolean }>("/api/auth/logout"),
  authStatus: () => get<{ authenticated: boolean }>("/api/auth/status"),

  // ---- Admin: groups ----
  groups: () => get<Group[]>("/api/admin/groups"),
  groupTree: () => get<GroupTree[]>("/api/admin/groups/tree"),
  createGroup: (b: Partial<Group>) => post<Group>("/api/admin/groups", b),
  updateGroup: (id: string, b: Partial<Group>) => patch<Group>(`/api/admin/groups/${id}`, b),
  deleteGroup: (id: string) => del(`/api/admin/groups/${id}`),

  // ---- Admin: users ----
  users: (params?: { group_id?: string; q?: string }) =>
    get<UserRead[]>(`/api/admin/users${query(params)}`),
  user: (id: string) => get<UserDetail>(`/api/admin/users/${id}`),
  createUser: (b: { name: string; group_id?: string | null; barcode?: string | null }) =>
    post<UserDetail>("/api/admin/users", b),
  updateUser: (id: string, b: Record<string, unknown>) =>
    patch<UserDetail>(`/api/admin/users/${id}`, b),
  deleteUser: (id: string) => del(`/api/admin/users/${id}`),
  regenerateUserBarcode: (id: string) => post<UserDetail>(`/api/admin/users/${id}/barcode`),
  userEvents: (id: string) => get<ItemEvent[]>(`/api/admin/users/${id}/events`),
  userBarcodeSvg: (id: string) => `${BASE}/api/admin/users/${id}/barcode.svg`,
  batchUpdateUsers: (ids: string[], patch: { group_id?: string | null; status?: UserStatus }) =>
    request<UserRead[]>("/api/admin/users/batch", {
      method: "PATCH",
      body: JSON.stringify({ ids, patch }),
    }),
  batchDeleteUsers: (ids: string[]) => post<void>("/api/admin/users/batch-delete", { ids }),
  usersXlsx: () => requestBlob("/api/admin/users.xlsx"),
  importUsers: (file: File) => postForm<ImportResult>("/api/admin/users/import", form(file)),
  userIdCardPdf: (id: string) => requestBlob(`/api/admin/users/${id}/id-card.pdf`),
  groupIdCardsPdf: (groupId: string) => requestBlob(`/api/admin/groups/${groupId}/id-cards.pdf`),
  usersIdCardsPdf: (ids: string[]) => requestBlobPost("/api/admin/users/id-cards.pdf", { ids }),

  // ---- Admin: inventory ----
  itemTypes: (q?: string) => get<ItemType[]>(`/api/admin/item-types${query({ q })}`),
  createItemType: (b: Record<string, unknown>) => post<ItemType>("/api/admin/item-types", b),
  updateItemType: (id: string, b: Record<string, unknown>) =>
    patch<ItemType>(`/api/admin/item-types/${id}`, b),
  deleteItemType: (id: string) => del(`/api/admin/item-types/${id}`),
  adminItems: (params?: { q?: string; type_id?: string; location?: string }) =>
    get<Item[]>(`/api/admin/items${query(params)}`),
  createItem: (b: Record<string, unknown>) => post<Item>("/api/admin/items", b),
  updateItem: (id: string, b: Record<string, unknown>) => patch<Item>(`/api/admin/items/${id}`, b),
  deleteItem: (id: string) => del(`/api/admin/items/${id}`),
  adminItemEvents: (id: string) => get<ItemEvent[]>(`/api/admin/items/${id}/events`),
  itemBarcodeSvg: (id: string) => `${BASE}/api/admin/items/${id}/barcode.svg`,
  locations: () => get<string[]>("/api/admin/locations"),
  manufacturers: () => get<string[]>("/api/admin/manufacturers"),
  setItemStatus: (id: string, status: ItemStatus, note?: string) =>
    post<Item>(`/api/admin/items/${id}/status`, { status, note }),
  batchItemStatus: (ids: string[], status: ItemStatus, note?: string) =>
    post<Item[]>("/api/admin/items/batch/status", { ids, status, note }),
  batchUpdateItems: (
    ids: string[],
    patch: {
      item_type_id?: string;
      location?: string | null;
      condition?: Condition;
      needs_review?: boolean;
    },
  ) =>
    request<Item[]>("/api/admin/items/batch", {
      method: "PATCH",
      body: JSON.stringify({ ids, patch }),
    }),
  batchDeleteItems: (ids: string[]) => post<void>("/api/admin/items/batch-delete", { ids }),
  itemsXlsx: () => requestBlob("/api/admin/items.xlsx"),
  importItems: (file: File) => postForm<ImportResult>("/api/admin/items/import", form(file)),
  itemTagPdf: (id: string) => requestBlob(`/api/admin/items/${id}/tag.pdf`),
  itemTypeTagsPdf: (typeId: string) => requestBlob(`/api/admin/item-types/${typeId}/tags.pdf`),
  itemsTagsPdf: (ids: string[]) => requestBlobPost("/api/admin/items/tags.pdf", { ids }),

  // ---- Admin: history log ----
  adminEvents: (params?: {
    event_type?: string;
    user_id?: string;
    item_id?: string;
    date_from?: string;
    date_to?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => get<Page<ItemEvent>>(`/api/admin/events${query(params)}`),

  // ---- Admin: settings ----
  getSettings: () => get<AppSettings>("/api/admin/settings"),
  updateSettings: (patch: Partial<AppSettings>) =>
    request<AppSettings>("/api/admin/settings", { method: "PATCH", body: JSON.stringify(patch) }),

  // ---- Admin: card/label PDFs ----
  labelsPdf: () => requestBlob("/api/admin/labels.pdf"),

  // ---- Kiosk ----
  scan: (barcode: string, active_user_id?: string | null) =>
    post<ScanResponse>("/api/kiosk/scan", { barcode, active_user_id: active_user_id ?? null }),
  kioskUser: (id: string) => get<UserDetail>(`/api/kiosk/user/${id}`),
  kioskUserEvents: (id: string) => get<ItemEvent[]>(`/api/kiosk/user/${id}/events`),
  kioskCheckout: (item_id: string, user_id: string) =>
    post<Item>("/api/kiosk/checkout", { item_id, user_id }),
  kioskCheckin: (item_id: string, user_id: string) =>
    post<Item>("/api/kiosk/checkin", { item_id, user_id }),
  kioskReportDamage: (item_id: string, user_id?: string | null, note?: string) =>
    post<Item>("/api/kiosk/report-damage", { item_id, user_id: user_id ?? null, note }),
  kioskReportLoss: (item_id: string, user_id?: string | null, note?: string) =>
    post<Item>("/api/kiosk/report-loss", { item_id, user_id: user_id ?? null, note }),

  // ---- Inventory (read-only) ----
  inventoryItems: (params?: { q?: string; type_id?: string; location?: string }) =>
    get<Item[]>(`/api/inventory/items${query(params)}`),
  inventoryItem: (id: string) => get<Item>(`/api/inventory/items/${id}`),
  inventoryItemEvents: (id: string) => get<ItemEvent[]>(`/api/inventory/items/${id}/events`),
  inventorySummary: () => get<InventorySummaryRow[]>("/api/inventory/summary"),
  inventoryLocations: () => get<string[]>("/api/inventory/locations"),
};

function query(params?: Record<string, string | number | undefined | null>): string {
  if (!params) return "";
  const pairs = Object.entries(params).filter(([, v]) => v != null && v !== "");
  if (pairs.length === 0) return "";
  return "?" + pairs.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
}

function form(file: File): FormData {
  const data = new FormData();
  data.append("file", file);
  return data;
}
