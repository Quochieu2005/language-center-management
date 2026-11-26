import sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ev_harness as h

COMMON_BEFORE_30 = ["07_add_auth_session_tables.sql", "08_promote_admin_role_to_admin_big.sql",
                    "09_add_account_slug_and_rename_password_column.sql", "10_add_public_slugs.sql",
                    "12_admin_password_reset_otp.sql", "18_add_notifications.sql", "19_enable_student_accounts.sql",
                    "24_account_status_bit.sql", "26_consolidate_logs_and_remove_notification_reads.sql",
                    "27_move_oauth_identity_to_account.sql", "28_add_tuition_installments.sql",
                    "29_extend_employee_roles.sql"]
AFTER_30 = ["31_add_account_avatar_metadata.sql", "31_add_sepay_tuition_payments.sql",
            "33_add_course_duration_fields.sql", "34_allow_fractional_course_months.sql",
            "35_allow_optional_course_session_count.sql", "36_add_blog_tables.sql",
            "37_merge_consultant_and_placement_roles.sql", "38_add_student_avatar_metadata.sql",
            "39_add_contact_inbox.sql", "40_enable_tuition_refunds.sql",
            "41_merge_receptionist_into_accounting.sql", "42_add_site_staff_notification_audience.sql",
            "43_enforce_contact_site_boundary.sql", "44_revalidate_course_subject_fk.sql",
            "47_add_blog_cover_image.sql", "48_add_nguoi_dung_account_scope.sql"]
AUTHORITY_ONLY = ["45_account_replication_queue.sql", "49_create_nguoi_dung_profile.sql"]

only = sys.argv[1:] or list(h.SITES)
for code in only:
    name = h.SITES[code]
    seq = COMMON_BEFORE_30 + ["@seed"] + ["30_enforce_site_fragment_boundaries.sql"] + AFTER_30
    if code == "EVA":
        seq += AUTHORITY_ONLY
    for f in seq:
        try:
            if f == "@seed":
                conn = h.connect(name)
                cur = conn.cursor()
                for c2 in h.SITES:
                    cur.execute(
                        "INSERT dbo.CoSo(ma_co_so, slug, ten_co_so, dia_chi, sdt, trang_thai) VALUES (?,?,?,?,?, 'hoat_dong')",
                        c2, "co-so-" + c2.lower(), "Co so " + c2, "Dia chi " + c2, "0900000000")
                conn.close()
                print(code, "seed CoSo ok")
            else:
                n = h.run_script(name, f)
                print(code, f, "ok", n)
        except Exception as exc:
            print(code, f, "FAILED:", str(exc)[:300].replace("\n", " "))
            break
