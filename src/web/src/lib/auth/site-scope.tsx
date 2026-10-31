"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { adminApi } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "./session";

type SiteScope = { siteCodes: string[]; selectedSite: string | null; setSelectedSite: (site: string) => void; loadingSites: boolean };
const SiteContext = createContext<SiteScope | null>(null);

export function SiteScopeProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const [bigSiteCodes, setBigSiteCodes] = useState<string[]>([]);
  const [bigSelectedSite, setBigSelectedSite] = useState<string | null>(null);
  const [sitesLoaded, setSitesLoaded] = useState(false);
  const localSiteCodes = user?.site_code ? [user.site_code] : [];
  const siteCodes = user?.role === "admin_big" ? bigSiteCodes : localSiteCodes;
  const selectedSite = user?.role === "admin_big" ? bigSelectedSite : user?.site_code || null;
  const loadingSites = user?.role === "admin_big" && !sitesLoaded;
  useEffect(() => {
    if (user?.role !== "admin_big") return;
    let cancelled = false;
    adminApi.studentCounts().then((result) => {
      if (cancelled) return;
      setBigSiteCodes(result.site_codes);
      const saved = sessionStorage.getItem("qlttnn.selected-site");
      setBigSelectedSite(saved && result.site_codes.includes(saved) ? saved : result.site_codes[0] || null);
    }).catch((error: unknown) => {
      if (cancelled) return;
      const partial = error instanceof ApiError && Array.isArray(error.payload.site_codes) ? error.payload.site_codes.filter((code): code is string => typeof code === "string") : [];
      setBigSiteCodes(partial);
      setBigSelectedSite(partial[0] || null);
    })
      .finally(() => { if (!cancelled) setSitesLoaded(true); });
    return () => { cancelled = true; };
  }, [user?.role]);
  const setSelectedSite = useCallback((site: string) => {
    if (user?.role !== "admin_big" || !siteCodes.includes(site)) return;
    sessionStorage.setItem("qlttnn.selected-site", site);
    setBigSelectedSite(site);
  }, [siteCodes, user?.role]);
  const value = useMemo(() => ({ siteCodes, selectedSite, setSelectedSite, loadingSites }), [siteCodes, selectedSite, setSelectedSite, loadingSites]);
  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useSiteScope() {
  const context = useContext(SiteContext);
  if (!context) throw new Error("useSiteScope phải nằm trong SiteScopeProvider.");
  return context;
}
