"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alert, Spin } from "antd";
import AccountProfile, { type ProfileValues } from "@/components/web/account/AccountProfile";
import WebFooter from "@/components/web/layout/WebFooter";
import WebHeader from "@/components/web/layout/WebHeader";
import pageStyles from "@/components/web/catalog/PublicInfoPage.module.scss";
import { academicsApi, type ApiRow } from "@/lib/api/academics";
import { ApiError } from "@/lib/api/client";
import { RequireSession, useSession } from "@/lib/auth/session";

export default function AccountRoute() {
  return <RequireSession roles={["hoc_vien"]}><AccountPage /></RequireSession>;
}

function AccountPage() {
  const { user } = useSession();
  const slug = user?.slug ?? "";
  const [profile, setProfile] = useState<ApiRow | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!slug) return;
    try {
      setProfile(await academicsApi.studentProfile(slug));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Chưa tải được hồ sơ.");
    }
  }, [slug]);

  useEffect(() => { queueMicrotask(() => void load()); }, [load]);

  const save = async (values: ProfileValues) => {
    setSaving(true);
    try {
      setProfile(await academicsApi.updateStudentProfile(slug, values));
      return null;
    } catch (reason) {
      if (reason instanceof ApiError) {
        const fields = Object.values(reason.payload).filter(Array.isArray).map((value) => (value as string[]).join(" ")).join(" ");
        return fields || reason.message;
      }
      return reason instanceof Error ? reason.message : "Không lưu được hồ sơ.";
    } finally {
      setSaving(false);
    }
  };

  return <div className={pageStyles.page}>
    <WebHeader />
    <main id="main-content" className={pageStyles.main}>
      <div className={pageStyles.breadcrumb}><Link href="/">Trang chủ</Link><span>/</span><span>Hồ sơ của bạn</span></div>
      <section className={pageStyles.hero}>
        <p className={pageStyles.eyebrow}>TÀI KHOẢN CỦA BẠN</p>
        <h1>Hồ sơ<br /><span>của bạn.</span></h1>
        <p className={pageStyles.lead}>Cập nhật ảnh và thông tin để trung tâm liên hệ và hỗ trợ bạn khi chọn khóa học.</p>
      </section>
      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 20 }} />}
      {profile ? <AccountProfile profile={profile} slug={slug} saving={saving} onSave={save} />
        : !error && <div style={{ padding: 60, textAlign: "center" }}><Spin /></div>}
    </main>
    <WebFooter />
  </div>;
}
