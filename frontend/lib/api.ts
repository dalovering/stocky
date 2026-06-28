// Typed client for the Stocky API. Cookies (the admin session) are sent with every
// request via `credentials: "include"`.

import type {
  Group,
  GroupTree,
  InventorySummaryRow,
  Item,
  ItemEvent,
  ItemType,
  ScanResponse,
  UserDetail,
  UserRead,
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

  // ---- Admin: barcode-label sheet (PDF of every user + item barcode) ----
  labelsPdf: () => requestBlob("/api/admin/labels.pdf"),

  // ---- Kiosk ----
  scan: (barcode: string, active_user_id?: string | null) =>
    post<ScanResponse>("/api/kiosk/scan", { barcode, active_user_id: active_user_id ?? null }),
  kioskUser: (id: string) => get<UserDetail>(`/api/kiosk/user/${id}`),
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

function query(params?: Record<string, string | undefined | null>): string {
  if (!params) return "";
  const pairs = Object.entries(params).filter(([, v]) => v != null && v !== "");
  if (pairs.length === 0) return "";
  return "?" + pairs.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
}
