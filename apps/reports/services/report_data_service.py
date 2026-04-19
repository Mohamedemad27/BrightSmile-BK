import base64
from collections import defaultdict
from datetime import date
from pathlib import Path

from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.core.models import Appointment, DoctorReview, MedicalHistory
from apps.dashboard.models import AuditLog
from apps.users.models import Doctor, Patient


class ReportDataService:
    CIRC = 376.99
    _logo_cache = None

    @staticmethod
    def _f(v):
        return float(v or 0)

    @classmethod
    def _segs(cls, pairs):
        total = sum(v for _, v in pairs) or 1
        off = 0
        out = []
        for i, (label, value) in enumerate(pairs, start=1):
            pct = round((value / total) * 100, 2) if total else 0
            dash = round((pct / 100) * cls.CIRC, 2)
            out.append(
                {
                    "label": label,
                    "value": value,
                    "percentage": pct,
                    "color_idx": ((i - 1) % 8) + 1,
                    "dash": dash,
                    "offset": off,
                }
            )
            off = round(off + dash, 2)
        return out

    @staticmethod
    def _bars(items, key):
        m = max((i.get(key, 0) or 0 for i in items), default=0) or 1
        for i in items:
            i["bar_percent"] = round(((i.get(key, 0) or 0) / m) * 100, 2)
        return items

    @staticmethod
    def _base(title, user, filters):
        now = timezone.now()
        period = (
            f"{filters.get('date_from', '...')} to {filters.get('date_to', '...')}"
            if filters.get("date_from") or filters.get("date_to")
            else "All time"
        )
        return {
            "report_title": title,
            "report_subtitle": "Generated from Bright Smile API",
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "generated_by": user.get_full_name() or user.email,
            "report_period": period,
            "year": str(now.year),
            "logo_base64": ReportDataService._logos().get("logo_base64", ""),
            "app_logo_base64": ReportDataService._logos().get("app_logo_base64", ""),
        }

    @classmethod
    def _logos(cls):
        if cls._logo_cache is not None:
            return cls._logo_cache

        base_dir = Path(__file__).resolve().parents[3]
        candidates = [
            base_dir / "templates",
            base_dir.parent / "Reports",
        ]

        def _read_b64(path):
            try:
                return base64.b64encode(path.read_bytes()).decode("utf-8")
            except Exception:
                return ""

        logo_b64 = ""
        app_logo_b64 = ""
        for root in candidates:
            if not logo_b64:
                p = root / "mti-logo-light-roboto.png"
                if p.exists():
                    logo_b64 = _read_b64(p)
            if not app_logo_b64:
                p = root / "smilix_logo.svg"
                if p.exists():
                    app_logo_b64 = _read_b64(p)
            if logo_b64 and app_logo_b64:
                break

        cls._logo_cache = {
            "logo_base64": logo_b64,
            "app_logo_base64": app_logo_b64,
        }
        return cls._logo_cache

    @staticmethod
    def _aq(filters):
        qs = Appointment.objects.select_related("doctor__user", "patient").prefetch_related("services")
        if filters.get("status"):
            qs = qs.filter(status=filters["status"])
        if filters.get("date_from"):
            qs = qs.filter(date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(date__lte=filters["date_to"])
        return qs

    @staticmethod
    def _services_obj(services_qs):
        return {"all": [{"name": s.name} for s in services_qs]}

    @staticmethod
    def _audit_q(filters):
        qs = AuditLog.objects.select_related("user").order_by("-created_at")
        if filters.get("date_from"):
            qs = qs.filter(created_at__date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(created_at__date__lte=filters["date_to"])
        return qs

    @classmethod
    def build_admin_appointments(cls, *, user, filters):
        limit = min(int(filters.get("limit", 200)), 1000)
        qs = cls._aq(filters)
        total = qs.count()
        counts = {k: qs.filter(status=k).count() for k in ["completed", "pending", "cancelled", "confirmed", "rejected"]}
        statuses = []
        for k in ["completed", "pending", "cancelled", "confirmed", "rejected"]:
            c = counts[k]
            statuses.append(
                {
                    "status": k,
                    "count": c,
                    "percentage": round((c / total) * 100, 2) if total else 0,
                    "revenue": cls._f(qs.filter(status=k).aggregate(v=Sum("total_price"))["v"]),
                }
            )
        docs = list(
            qs.values("doctor__user__first_name", "doctor__user__last_name", "doctor__specialty")
            .annotate(total=Count("id"), completed=Count("id", filter=Q(status="completed")), revenue=Sum("total_price"))
            .order_by("-total")[:10]
        )
        top_doctors = [
            {
                "name": f"{d['doctor__user__first_name']} {d['doctor__user__last_name']}".strip(),
                "specialty": d.get("doctor__specialty") or "-",
                "total": d["total"],
                "completed": d["completed"],
                "completion_rate": round((d["completed"] / d["total"]) * 100, 2) if d["total"] else 0,
                "revenue": cls._f(d["revenue"]),
            }
            for d in docs
        ]
        monthly_raw = list(
            qs.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Count("id"), completed=Count("id", filter=Q(status="completed")), cancelled=Count("id", filter=Q(status="cancelled")), revenue=Sum("total_price"))
            .order_by("month")
        )
        monthly = [
            {
                "label": r["month"].strftime("%b %Y"),
                "total": r["total"],
                "completed": r["completed"],
                "cancelled": r["cancelled"],
                "completion_rate": round((r["completed"] / r["total"]) * 100, 2) if r["total"] else 0,
                "revenue": cls._f(r["revenue"]),
            }
            for r in monthly_raw
        ]
        svc_rows = list(
            qs.values("services__name", "services__price", "doctor__user__first_name", "doctor__user__last_name")
            .annotate(count=Count("id"), total_revenue=Sum("services__price"))
            .filter(services__name__isnull=False)
            .order_by("-count")[:10]
        )
        popular_services = [
            {
                "name": r["services__name"],
                "doctor_name": f"{r['doctor__user__first_name']} {r['doctor__user__last_name']}".strip(),
                "count": r["count"],
                "price": cls._f(r["services__price"]),
                "total_revenue": cls._f(r["total_revenue"]),
            }
            for r in svc_rows
        ]
        appts = []
        for a in qs.order_by("-date", "-created_at")[:limit]:
            appts.append(
                {
                    "date": a.date,
                    "time_slot": a.time_slot,
                    "status": a.status,
                    "total_price": cls._f(a.total_price),
                    "patient": {"first_name": a.patient.first_name, "last_name": a.patient.last_name},
                    "doctor": {"user": {"first_name": a.doctor.user.first_name, "last_name": a.doctor.user.last_name}},
                    "services": cls._services_obj(a.services.all()),
                    "notes": a.notes,
                }
            )
        data = cls._base("Admin Appointments Report", user, filters)
        data.update(
            {
                "total_appointments": total,
                "completed_count": counts["completed"],
                "pending_count": counts["pending"],
                "cancelled_count": counts["cancelled"],
                "confirmed_count": counts["confirmed"],
                "rejected_count": counts["rejected"],
                "total_revenue": cls._f(qs.aggregate(v=Sum("total_price"))["v"]),
                "status_breakdown": statuses,
                "status_chart_segments": cls._segs([(s["status"].title(), s["count"]) for s in statuses if s["count"] > 0]),
                "doctors_chart": cls._bars([{"name": d["name"], "count": d["total"]} for d in top_doctors[:8]], "count"),
                "monthly_chart": cls._bars([{"label": m["label"], "total": m["total"]} for m in monthly], "total"),
                "revenue_chart": cls._bars([{"label": m["label"], "revenue": m["revenue"]} for m in monthly], "revenue"),
                "services_chart": cls._bars([{"name": s["name"], "count": s["count"]} for s in popular_services[:8]], "count"),
                "top_doctors": top_doctors,
                "appointments": appts,
                "monthly_trend": monthly,
                "popular_services": popular_services,
            }
        )
        return data

    @classmethod
    def build_admin_patients(cls, *, user, filters):
        limit = min(int(filters.get("limit", 200)), 1000)
        qs = Patient.objects.select_related("user").all()
        if filters.get("date_from"):
            qs = qs.filter(created_at__date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(created_at__date__lte=filters["date_to"])
        total = qs.count()
        active = qs.filter(user__is_active=True).count()
        verified = qs.filter(user__is_verified=True).count()
        month_start = date.today().replace(day=1)
        new_month = qs.filter(created_at__date__gte=month_start).count()
        appt_qs = cls._aq(filters)
        conditions = [
            ("diabetes", "Diabetes"),
            ("heart_disease", "Heart Disease"),
            ("blood_pressure", "Blood Pressure"),
            ("allergies", "Allergies"),
            ("bleeding_disorders", "Bleeding Disorders"),
            ("asthma", "Asthma"),
            ("pregnancy", "Pregnancy"),
            ("smoking", "Smoking"),
            ("previous_dental_surgery", "Previous Dental Surgery"),
        ]
        cond_overview = []
        for f, label in conditions:
            c = MedicalHistory.objects.filter(**{f: True}).count()
            if c > 0:
                cond_overview.append({"name": label, "count": c, "percentage": round((c / total) * 100, 2) if total else 0})
        reg_raw = list(qs.annotate(month=TruncMonth("created_at")).values("month").annotate(new_patients=Count("user_id")).order_by("month"))
        run = 0
        reg = []
        for r in reg_raw:
            run += r["new_patients"]
            reg.append({"label": r["month"].strftime("%b %Y"), "new_patients": r["new_patients"], "cumulative": run})
        patients = []
        for p in qs.order_by("-created_at")[:limit]:
            patients.append(
                {
                    "user": {"first_name": p.user.first_name, "last_name": p.user.last_name, "email": p.user.email, "is_active": p.user.is_active},
                    "phone_number": p.phone_number,
                    "date_of_birth": p.date_of_birth,
                    "created_at": p.created_at,
                    "appointment_count": Appointment.objects.filter(patient=p.user).count(),
                    "ai_scan_count": 0,
                }
            )
        data = cls._base("Admin Patients Report", user, filters)
        data.update(
            {
                "total_patients": total,
                "active_patients": active,
                "verified_patients": verified,
                "new_this_month": new_month,
                "total_appointments": appt_qs.count(),
                "total_revenue": cls._f(appt_qs.filter(status="completed").aggregate(v=Sum("total_price"))["v"]),
                "total_ai_scans": 0,
                "status_chart_segments": cls._segs([("Active", active), ("Inactive", max(total - active, 0))]),
                "conditions_chart": cls._bars([{"name": c["name"], "percentage": c["percentage"]} for c in cond_overview[:8]], "percentage"),
                "registration_chart": cls._bars([{"label": r["label"], "new_patients": r["new_patients"]} for r in reg], "new_patients"),
                "patients": patients,
                "conditions_overview": cond_overview,
                "registration_trend": reg,
            }
        )
        return data

    @classmethod
    def build_admin_audit(cls, *, user, filters):
        limit = min(int(filters.get("limit", 200)), 1000)
        qs = cls._audit_q(filters)
        total = qs.count()
        failed_q = Q(action__icontains="fail") | Q(description__icontains="failed")
        security_q = failed_q | Q(action__icontains="security") | Q(action__icontains="login") | Q(action__icontains="password") | Q(action__icontains="otp")
        act = list(qs.values("action").annotate(count=Count("id"), unique_users=Count("user_id", distinct=True)).order_by("-count"))
        act_total = sum(i["count"] for i in act) or 1
        breakdown = [
            {
                "name": a["action"],
                "category": "security" if "login" in (a["action"] or "").lower() else "system",
                "count": a["count"],
                "percentage": round((a["count"] / act_total) * 100, 2),
                "unique_users": a["unique_users"],
            }
            for a in act[:20]
        ]
        cat_count = defaultdict(int)
        for b in breakdown:
            cat_count[b["category"]] += b["count"]
        # Django QuerySets do not support negative slicing (e.g. [-14:]).
        # Fetch the last 14 days at the DB level, then reverse for ascending display.
        daily = list(
            qs.extra(select={"day": "DATE(created_at)"})
            .values("day")
            .annotate(count=Count("id"))
            .order_by("-day")[:14]
        )
        daily.reverse()
        users = list(qs.exclude(user__isnull=True).values("user_id", "user__first_name", "user__last_name", "user__user_type").annotate(total_actions=Count("id"), last_activity=Max("created_at")).order_by("-total_actions")[:20])

        def logs(it):
            return [
                {
                    "created_at": l.created_at,
                    "action": l.action,
                    "description": l.description,
                    "ip_address": l.ip_address,
                    "target_type": l.target_type,
                    "target_id": l.target_id,
                    "user": {"first_name": getattr(l.user, "first_name", ""), "last_name": getattr(l.user, "last_name", "")} if l.user else None,
                }
                for l in it
            ]

        data = cls._base("Admin Audit Report", user, filters)
        data.update(
            {
                "total_events": total,
                "unique_users": qs.exclude(user__isnull=True).values("user_id").distinct().count(),
                "security_events": qs.filter(security_q).count(),
                "failed_events": qs.filter(failed_q).count(),
                "category_chart_segments": cls._segs([(k.title(), v) for k, v in cat_count.items()]),
                "top_actions_chart": cls._bars([{"name": b["name"], "count": b["count"]} for b in breakdown[:8]], "count"),
                "daily_activity_chart": cls._bars([{"label": str(d["day"]), "count": d["count"]} for d in daily], "count"),
                "active_users_chart": cls._bars([{"name": f"{u['user__first_name']} {u['user__last_name']}".strip(), "actions": u["total_actions"]} for u in users[:8]], "actions"),
                "security_ratio": {
                    "normal_pct": round((max(total - qs.filter(security_q).count(), 0) / total) * 100, 2) if total else 0,
                    "security_pct": round((qs.filter(security_q).count() / total) * 100, 2) if total else 0,
                    "failed_pct": round((qs.filter(failed_q).count() / total) * 100, 2) if total else 0,
                },
                "action_breakdown": breakdown,
                "security_logs": logs(qs.filter(security_q)[:limit]),
                "user_management_logs": logs(qs.filter(Q(action__icontains="user") | Q(action__icontains="role") | Q(action__icontains="doctor"))[:limit]),
                "appointment_logs": logs(qs.filter(action__icontains="appointment")[:limit]),
                "audit_logs": logs(qs[:limit]),
                "most_active_users": [
                    {
                        "name": f"{u['user__first_name']} {u['user__last_name']}".strip(),
                        "role": u["user__user_type"],
                        "total_actions": u["total_actions"],
                        "most_common_action": (qs.filter(user_id=u["user_id"]).values("action").annotate(c=Count("id")).order_by("-c").first() or {}).get("action", "-"),
                        "last_activity": u["last_activity"],
                    }
                    for u in users
                ],
            }
        )
        return data

    @classmethod
    def build_admin_doctors(cls, *, user, filters):
        limit = min(int(filters.get("limit", 200)), 1000)
        qs = Doctor.objects.select_related("user")
        total = qs.count()
        active = qs.filter(user__is_active=True).count()
        inactive = max(total - active, 0)
        avg_rating = round((sum(float(d.rating) for d in qs) / total), 2) if total else 0
        total_reviews = sum(int(d.total_reviews) for d in qs)
        total_specialties = qs.exclude(specialty="").values("specialty").distinct().count()
        specialty = []
        for row in qs.values("specialty").exclude(specialty="").annotate(count=Count("user_id")).order_by("-count"):
            ids = list(qs.filter(specialty=row["specialty"]).values_list("user_id", flat=True))
            aq = Appointment.objects.filter(doctor__user_id__in=ids)
            specialty.append(
                {
                    "specialty": row["specialty"],
                    "count": row["count"],
                    "avg_rating": round(sum(float(d.rating) for d in qs.filter(specialty=row["specialty"])) / row["count"], 2) if row["count"] else 0,
                    "total_appointments": aq.count(),
                    "total_revenue": cls._f(aq.filter(status="completed").aggregate(v=Sum("total_price"))["v"]),
                }
            )
        doctors = []
        for d in qs.order_by("-created_at")[:limit]:
            aq = Appointment.objects.filter(doctor=d)
            doctors.append(
                {
                    "user": {"first_name": d.user.first_name, "last_name": d.user.last_name, "email": d.user.email},
                    "specialty": d.specialty,
                    "rating": float(d.rating),
                    "total_reviews": d.total_reviews,
                    "license_status": getattr(d, "license_status", "active"),
                    "syndicate_number": getattr(d, "syndicate_number", "-"),
                    "created_at": d.created_at,
                    "total_appointments": aq.count(),
                    "total_revenue": cls._f(aq.filter(status="completed").aggregate(v=Sum("total_price"))["v"]),
                }
            )
        data = cls._base("Admin Doctors Report", user, filters)
        data.update(
            {
                "total_doctors": total,
                "active_doctors": active,
                "pending_approval": inactive,
                "inactive_doctors": inactive,
                "total_specialties": total_specialties,
                "avg_rating": avg_rating,
                "total_reviews": total_reviews,
                "status_chart_segments": cls._segs([("Active", active), ("Inactive", inactive)]),
                "specialty_chart": cls._bars([{"name": s["specialty"], "count": s["count"]} for s in specialty[:8]], "count"),
                "rating_chart": cls._bars([{"name": f"{d.user.first_name} {d.user.last_name}".strip(), "rating": float(d.rating)} for d in qs.order_by("-rating", "-total_reviews")[:8]], "rating"),
                "specialty_breakdown": specialty,
                "doctors": doctors,
                "top_doctors": sorted(doctors, key=lambda x: (x["rating"], x["total_reviews"]), reverse=True)[:10],
            }
        )
        return data

    @classmethod
    def build_doctor_appointments(cls, *, user, filters):
        d = user.doctor_profile
        limit = min(int(filters.get("limit", 200)), 1000)
        qs = cls._aq(filters).filter(doctor=d)
        total = qs.count()
        counts = {k: qs.filter(status=k).count() for k in ["completed", "pending", "cancelled", "confirmed", "rejected"]}
        status_breakdown = [
            {
                "status": k,
                "count": counts[k],
                "percentage": round((counts[k] / total) * 100, 2) if total else 0,
                "revenue": cls._f(qs.filter(status=k).aggregate(v=Sum("total_price"))["v"]),
            }
            for k in ["completed", "pending", "cancelled", "confirmed", "rejected"]
        ]
        monthly_raw = list(
            qs.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Count("id"), completed=Count("id", filter=Q(status="completed")), cancelled=Count("id", filter=Q(status="cancelled")), revenue=Sum("total_price"))
            .order_by("month")
        )
        monthly = [
            {
                "label": r["month"].strftime("%b %Y"),
                "total": r["total"],
                "completed": r["completed"],
                "cancelled": r["cancelled"],
                "completion_rate": round((r["completed"] / r["total"]) * 100, 2) if r["total"] else 0,
                "revenue": cls._f(r["revenue"]),
            }
            for r in monthly_raw
        ]
        svc_rows = list(
            qs.values("services__name", "services__price")
            .annotate(count=Count("id"), total_revenue=Sum("services__price"))
            .filter(services__name__isnull=False)
            .order_by("-count")
        )
        services = [{"name": r["services__name"], "count": r["count"], "price": cls._f(r["services__price"]), "total_revenue": cls._f(r["total_revenue"])} for r in svc_rows]
        appts = [
            {
                "date": a.date,
                "time_slot": a.time_slot,
                "status": a.status,
                "total_price": cls._f(a.total_price),
                "patient": {"first_name": a.patient.first_name, "last_name": a.patient.last_name},
                "services": cls._services_obj(a.services.all()),
                "notes": a.notes,
            }
            for a in qs.order_by("-date", "-created_at")[:limit]
        ]
        data = cls._base("Doctor Appointments Report", user, filters)
        data.update(
            {
                "doctor": {"user": {"first_name": d.user.first_name, "last_name": d.user.last_name, "email": d.user.email}, "specialty": d.specialty, "phone_number": d.phone_number},
                "total_appointments": total,
                "completed_count": counts["completed"],
                "pending_count": counts["pending"],
                "cancelled_count": counts["cancelled"],
                "confirmed_count": counts["confirmed"],
                "rejected_count": counts["rejected"],
                "total_revenue": cls._f(qs.aggregate(v=Sum("total_price"))["v"]),
                "status_breakdown": status_breakdown,
                "status_chart_segments": cls._segs([(s["status"].title(), s["count"]) for s in status_breakdown if s["count"] > 0]),
                "services_chart": cls._bars([{"name": s["name"], "count": s["count"]} for s in services[:8]], "count"),
                "monthly_chart": cls._bars([{"label": m["label"], "total": m["total"]} for m in monthly], "total"),
                "revenue_chart": cls._bars([{"label": m["label"], "revenue": m["revenue"]} for m in monthly], "revenue"),
                "appointments": appts,
                "services_breakdown": services,
            }
        )
        return data

    @classmethod
    def build_doctor_patients(cls, *, user, filters):
        limit = min(int(filters.get("limit", 100)), 500)
        d = user.doctor_profile
        aq = Appointment.objects.filter(doctor=d).select_related("patient", "doctor__user").prefetch_related("services")
        if filters.get("date_from"):
            aq = aq.filter(date__gte=filters["date_from"])
        if filters.get("date_to"):
            aq = aq.filter(date__lte=filters["date_to"])
        rows = list(aq.values("patient_id", "patient__first_name", "patient__last_name", "patient__email").annotate(total_visits=Count("id"), last_visit=Max("date")).order_by("-last_visit")[:limit])
        pids = [r["patient_id"] for r in rows]
        profiles = {p.user_id: p for p in Patient.objects.filter(user_id__in=pids)}
        appts_by_patient = defaultdict(list)
        for a in aq.filter(patient_id__in=pids).order_by("-date", "-created_at"):
            appts_by_patient[a.patient_id].append({"date": a.date, "time_slot": a.time_slot, "status": a.status, "total_price": cls._f(a.total_price), "notes": a.notes, "services": [{"name": s.name} for s in a.services.all()]})
            appts_by_patient[a.patient_id][-1]["services"] = cls._services_obj(a.services.all())
        month_start = date.today().replace(day=1)
        new_count = 0
        patients = []
        for r in rows:
            fa = aq.filter(patient_id=r["patient_id"]).order_by("date").first()
            if fa and fa.date >= month_start:
                new_count += 1
            pr = profiles.get(r["patient_id"])
            patients.append({"full_name": f"{r['patient__first_name']} {r['patient__last_name']}".strip(), "email": r["patient__email"], "phone_number": getattr(pr, "phone_number", ""), "date_of_birth": getattr(pr, "date_of_birth", None), "total_visits": r["total_visits"], "last_visit": r["last_visit"], "appointments": appts_by_patient.get(r["patient_id"], [])})
        total = len(patients)
        returning = max(total - new_count, 0)
        data = cls._base("Doctor Patients Report", user, filters)
        data.update({"doctor": {"user": {"first_name": d.user.first_name, "last_name": d.user.last_name, "email": d.user.email}, "specialty": d.specialty, "phone_number": d.phone_number, "rating": float(d.rating), "total_reviews": d.total_reviews, "location": d.location}, "total_patients": total, "new_patients": new_count, "returning_patients": returning, "patient_chart_segments": cls._segs([("New", new_count), ("Returning", returning)]), "top_patients_chart": cls._bars([{"name": p["full_name"], "visits": p["total_visits"]} for p in patients[:10]], "visits"), "patients": patients})
        return data

    @classmethod
    def build_patient_report(cls, *, user, filters):
        limit = min(int(filters.get("limit", 200)), 1000)
        aq = Appointment.objects.filter(patient=user).select_related("doctor__user").prefetch_related("services")
        if filters.get("date_from"):
            aq = aq.filter(date__gte=filters["date_from"])
        if filters.get("date_to"):
            aq = aq.filter(date__lte=filters["date_to"])
        total = aq.count()
        completed = aq.filter(status="completed").count()
        upcoming = aq.filter(status__in=["pending", "confirmed"], date__gte=date.today()).count()
        cancelled = aq.filter(status="cancelled").count()
        spending = list(aq.values("doctor__user__first_name", "doctor__user__last_name").annotate(total=Sum("total_price")).order_by("-total")[:8])
        reviews = [{"created_at": r.created_at, "rating": r.rating, "comment": r.comment, "doctor": {"user": {"first_name": r.doctor.user.first_name, "last_name": r.doctor.user.last_name}}} for r in DoctorReview.objects.filter(user=user).select_related("doctor__user").order_by("-created_at")[:limit]]
        appts = [{"date": a.date, "time_slot": a.time_slot, "status": a.status, "total_price": cls._f(a.total_price), "doctor": {"user": {"first_name": a.doctor.user.first_name, "last_name": a.doctor.user.last_name}, "specialty": a.doctor.specialty}, "services": cls._services_obj(a.services.all())} for a in aq.order_by("-date", "-created_at")[:limit]]
        p = getattr(user, "patient_profile", None)
        mh = getattr(user, "medical_history", None)
        mh_data = None
        if mh:
            mh_data = {
                "diabetes": mh.diabetes,
                "heart_disease": mh.heart_disease,
                "blood_pressure": mh.blood_pressure,
                "allergies": mh.allergies,
                "bleeding_disorders": mh.bleeding_disorders,
                "asthma": mh.asthma,
                "pregnancy": mh.pregnancy,
                "smoking": mh.smoking,
                "previous_dental_surgery": mh.previous_dental_surgery,
                "notes": mh.notes,
            }
        data = cls._base("Patient Report", user, filters)
        data.update({"patient": {"user": {"first_name": user.first_name, "last_name": user.last_name, "email": user.email}, "phone_number": getattr(p, "phone_number", ""), "date_of_birth": getattr(p, "date_of_birth", None), "created_at": getattr(p, "created_at", user.created_at)}, "medical_history": mh_data, "total_appointments": total, "completed_appointments": completed, "upcoming_appointments": upcoming, "cancelled_appointments": cancelled, "status_chart_segments": cls._segs([("Completed", completed), ("Upcoming", upcoming), ("Cancelled", cancelled)]), "spending_chart": cls._bars([{"name": f"{s['doctor__user__first_name']} {s['doctor__user__last_name']}".strip(), "total": cls._f(s['total'])} for s in spending], "total"), "ai_confidence_chart": [], "appointments": appts, "ai_scans": [], "reviews": reviews})
        return data

    @classmethod
    def generate(cls, *, report_type, user, filters):
        handlers = {
            "admin_appointments": cls.build_admin_appointments,
            "admin_audit": cls.build_admin_audit,
            "admin_doctors": cls.build_admin_doctors,
            "admin_patients": cls.build_admin_patients,
            "doctor_appointments": cls.build_doctor_appointments,
            "doctor_patients": cls.build_doctor_patients,
            "patient_report": cls.build_patient_report,
        }
        if report_type not in handlers:
            raise ValueError(f"Unsupported report_type: {report_type}")
        return handlers[report_type](user=user, filters=filters)
