import { apiRequest, jsonBody, query } from "./client";

export type ContactSite = { site_code: string; name: string };
export type ContactSiteList = {
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  results: ContactSite[];
};
export type ContactSubmission = {
  site_code: string;
  full_name: string;
  email: string;
  phone?: string;
  subject: string;
  message: string;
};
export type ContactRequestStatus = "cho_xu_ly" | "da_phan_hoi";
export type ContactRequest = {
  request_id: string;
  status: ContactRequestStatus;
  received_at: string;
  site_code: string;
  full_name: string;
  email: string;
  phone: string | null;
  subject: string;
  message: string;
  reply_body: string | null;
  replied_at: string | null;
};
export type ContactRequestList = {
  scope: "LOCAL" | "GLOBAL";
  complete: boolean;
  missing_sites: string[];
  site_codes: string[];
  count: number | null;
  limit: number;
  offset: number;
  results: ContactRequest[];
};

export const contactsApi = {
  sites: () => apiRequest<ContactSiteList>("/contact/sites/"),
  submit: (body: ContactSubmission, idempotencyKey: string) =>
    apiRequest<{ request_id: string; site_code: string; status: ContactRequestStatus; received_at: string; replayed: boolean }>(
      "/contact/", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: jsonBody(body) },
    ),
  list: (options: { site_code?: string; status?: ContactRequestStatus; search?: string; limit?: number; offset?: number } = {}) =>
    apiRequest<ContactRequestList>(`/admin/contacts/${query(options)}`),
  reply: (siteCode: string, requestId: string, replyBody: string) =>
    apiRequest<{ request_id: string; site_code: string; status: "da_phan_hoi"; replied_at: string }>(
      `/admin/contacts/${encodeURIComponent(siteCode)}/${encodeURIComponent(requestId)}/reply/`,
      { method: "POST", body: jsonBody({ reply_body: replyBody }) },
    ),
};
