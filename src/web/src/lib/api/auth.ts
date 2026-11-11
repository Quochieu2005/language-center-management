import { apiRequest, jsonBody } from "./client";

export type Role = "admin_big" | "admin_small" | "le_tan" | "tu_van" | "ke_toan" | "xep_lop" | "giao_vien" | "hoc_vien";
export type SessionUser = {
  account_id: string;
  slug: string;
  email: string;
  username: string;
  role: Role;
  site_code: string | null;
  profile_id: string | null;
  must_change_password: boolean;
  avatar_secure_url?: string | null;
};
export type LoginResponse = { user: SessionUser; idle_timeout_seconds: number };
export type ProfileResponse = { user: SessionUser; expires_at: string };
export type AvatarUploadIntent = {
  intent_token: string;
  upload_url: string;
  cloud_name: string;
  api_key: string;
  fields: Record<string, string>;
  max_file_bytes: number;
};
export type OAuthProvider = "google" | "facebook";

export const authApi = {
  csrf: () => apiRequest<{ csrf_token: string }>("/auth/csrf/"),
  login: (identifier: string, password: string) =>
    apiRequest<LoginResponse>("/auth/login/", { method: "POST", body: jsonBody({ identifier, password }) }),
  profile: (slug: string) => apiRequest<ProfileResponse>(`/auth/profile/${encodeURIComponent(slug)}/`),
  createAvatarUploadIntent: (slug: string) =>
    apiRequest<AvatarUploadIntent>(`/auth/profile/${encodeURIComponent(slug)}/avatar/upload-intents/`, { method: "POST", body: "{}" }),
  completeAvatarUpload: (slug: string, body: { intent_token: string; public_id: string }) =>
    apiRequest<{ account_id: string; role: Role; avatar_secure_url: string; complete: boolean; site_codes: string[] }>(
      `/auth/profile/${encodeURIComponent(slug)}/avatar/complete/`, { method: "POST", body: jsonBody(body) },
    ),
  session: () => apiRequest<{ user: SessionUser }>("/auth/session/"),
  oauthLoginUrl: (provider: OAuthProvider) => `/auth/oauth/${provider}/start/`,
  startOAuthLink: (provider: OAuthProvider) =>
    apiRequest<{ authorization_url: string }>(`/auth/oauth/${provider}/start/`, { method: "POST", body: "{}" }),
  oauthConnections: (slug: string) =>
    apiRequest<{ connections: Record<OAuthProvider, boolean> }>(`/auth/oauth/connections/${encodeURIComponent(slug)}/`),
  activity: () => apiRequest<{ expires_at: string }>("/auth/activity/", { method: "POST", body: "{}" }),
  logout: () => apiRequest<{ detail: string }>("/auth/logout/", { method: "POST", body: "{}" }),
  changePassword: (current_password: string, new_password: string, confirm_password: string) =>
    apiRequest<{ detail: string }>("/auth/password/change/", {
      method: "POST", body: jsonBody({ current_password, new_password, confirm_password }),
    }),
  forgotPassword: (email: string) =>
    apiRequest<{ detail: string }>("/auth/password/forgot/", { method: "POST", body: jsonBody({ email }) }),
  resetPassword: (email: string, otp: string, new_password: string, confirm_password: string) =>
    apiRequest<{ detail: string }>("/auth/password/reset/", {
      method: "POST", body: jsonBody({ email, otp, new_password, confirm_password }),
    }),
};
