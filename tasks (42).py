"""
Analytics and reporting service layer for ClientHub CRM.
Performs complex aggregation queries for dashboards and reports.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.accounts.models import User
from apps.activities.models import ActivityLog
from apps.contacts.models import Company, Contact
from apps.deals.models import Deal, DealStage, Pipeline
from apps.tasks.models import Task

logger = logging.getLogger(__name__)


class ReportService:
    """
    Service for generating analytics data used in dashboards and reports.
    """

    @staticmethod
    def get_date_range(range_type, start_date=None, end_date=None):
        """Convert a date range type to actual start/end dates."""
        now = timezone.now()
        today = now.date()

        ranges = {
            "today": (today, today),
            "this_week": (today - timedelta(days=today.weekday()), today),
            "this_month": (today.replace(day=1), today),
            "this_quarter": (
                today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1),
                today,
            ),
            "this_year": (today.replace(month=1, day=1), today),
            "last_7_days": (today - timedelta(days=7), today),
            "last_30_days": (today - timedelta(days=30), today),
            "last_90_days": (today - timedelta(days=90), today),
        }

        if range_type == "custom" and start_date and end_date:
            return start_date, end_date

        return ranges.get(range_type, (today - timedelta(days=30), today))

    @classmethod
    def dashboard_summary(cls, user, date_range="this_month"):
        """
        Generate summary data for the main dashboard.
        Returns key metrics: total contacts, deals, revenue, tasks, etc.
        """
        start_date, end_date = cls.get_date_range(date_range)
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )

        # Build base querysets based on user role
        if user.role == User.Role.ADMIN:
            deals_qs = Deal.objects.all()
            contacts_qs = Contact.objects.all()
            tasks_qs = Task.objects.all()
        elif user.role == User.Role.SALES_MANAGER and user.team:
            team_members = User.objects.filter(team=user.team)
            deals_qs = Deal.objects.filter(owner__in=team_members)
            contacts_qs = Contact.objects.filter(owner__in=team_members)
            tasks_qs = Task.objects.filter(assigned_to__in=team_members)
        else:
            deals_qs = Deal.objects.filter(owner=user)
            contacts_qs = Contact.objects.filter(owner=user)
            tasks_qs = Task.objects.filter(assigned_to=user)

        # Period-filtered querysets
        period_deals = deals_qs.filter(created_at__range=(start_datetime, end_datetime))
        period_contacts = contacts_qs.filter(created_at__range=(start_datetime, end_datetime))

        # Won deals in period
        won_deals = deals_qs.filter(
            stage__is_won=True,
            actual_close_date__range=(start_date, end_date),
        )

        # Open deals
        open_deals = deals_qs.exclude(
            Q(stage__is_won=True) | Q(stage__is_lost=True)
        )

        return {
            "total_contacts": contacts_qs.count(),
            "new_contacts": period_contacts.count(),
            "total_deals": deals_qs.count(),
            "new_deals": period_deals.count(),
            "open_deals": open_deals.count(),
            "won_deals": won_deals.count(),
            "total_revenue": float(
                won_deals.aggregate(total=Sum("value")).get("total") or 0
            ),
            "pipeline_value": float(
                open_deals.aggregate(total=Sum("value")).get("total") or 0
            ),
            "weighted_pipeline_value": sum(
                float(d.weighted_value) for d in open_deals
            ),
            "tasks_pending": tasks_qs.filter(
                status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]
            ).count(),
            "tasks_overdue": tasks_qs.filter(
                due_date__lt=timezone.now(),
                status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS],
            ).count(),
            "tasks_completed": tasks_qs.filter(
                status=Task.Status.COMPLETED,
                completed_at__range=(start_datetime, end_datetime),
            ).count(),
            "avg_deal_value": float(
                won_deals.aggregate(avg=Avg("value")).get("avg") or 0
            ),
            "date_range": {
                "start": str(start_date),
                "end": str(end_date),
                "type": date_range,
            },
        }

    @classmethod
    def revenue_analytics(cls, user, date_range="this_month", group_by="day"):
        """
        Revenue data grouped by time period for charting.
        """
        start_date, end_date = cls.get_date_range(date_range)
        end_datetime = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )
        start_datetime = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )

        won_deals = Deal.objects.filter(
            stage__is_won=True,
            actual_close_date__range=(start_date, end_date),
        )

        if user.role != User.Role.ADMIN:
            if user.role == User.Role.SALES_MANAGER and user.team:
                team_members = User.objects.filter(team=user.team)
                won_deals = won_deals.filter(owner__in=team_members)
            else:
                won_deals = won_deals.filter(owner=user)

        trunc_fn = {
            "day": TruncDate,
            "week": TruncWeek,
            "month": TruncMonth,
        }.get(group_by, TruncDate)

        revenue_by_period = (
            won_deals.annotate(period=trunc_fn("actual_close_date"))
            .values("period")
            .annotate(
                revenue=Sum("value"),
                deal_count=Count("id"),
            )
            .order_by("period")
        )

        return {
            "data": [
                {
                    "period": str(item["period"]),
                    "revenue": float(item["revenue"]),
                    "deal_count": item["deal_count"],
                }
                for item in revenue_by_period
            ],
            "total_revenue": float(
                won_deals.aggregate(total=Sum("value")).get("total") or 0
            ),
            "total_deals": won_deals.count(),
            "avg_deal_size": float(
                won_deals.aggregate(avg=Avg("value")).get("avg") or 0
            ),
        }

    @classmethod
    def pipeline_funnel(cls, pipeline_id=None, user=None):
        """
        Pipeline funnel data showing deal count and value per stage.
        """
        if pipeline_id:
            try:
                pipeline = Pipeline.objects.get(id=pipeline_id)
            except Pipeline.DoesNotExist:
                return {"error": "Pipeline not found"}
        else:
            pipeline = Pipeline.objects.filter(is_default=True).first()
            if not pipeline:
                pipeline = Pipeline.objects.first()

        if not pipeline:
            return {"stages": [], "pipeline": None}

        stages = pipeline.stages.all().order_by("order")
        funnel = []

        for stage in stages:
            deals_qs = Deal.objects.filter(stage=stage)

            if user and user.role != User.Role.ADMIN:
                if user.role == User.Role.SALES_MANAGER and user.team:
                    team_members = User.objects.filter(team=user.team)
                    deals_qs = deals_qs.filter(owner__in=team_members)
                elif user.role != User.Role.SUPPORT_AGENT:
                    deals_qs = deals_qs.filter(owner=user)

            agg = deals_qs.aggregate(
                count=Count("id"),
                total_value=Sum("value"),
                avg_value=Avg("value"),
            )

            funnel.append(
                {
                    "stage_id": str(stage.id),
                    "stage_name": stage.name,
                    "stage_order": stage.order,
                    "probability": stage.probability,
                    "color": stage.color,
                    "is_won": stage.is_won,
                    "is_lost": stage.is_lost,
                    "deal_count": agg["count"],
                    "total_value": float(agg["total_value"] or 0),
                    "avg_value": float(agg["avg_value"] or 0),
                }
            )

        return {
            "pipeline": {
                "id": str(pipeline.id),
                "name": pipeline.name,
            },
            "stages": funnel,
        }

    @classmethod
    def sales_performance(cls, date_range="this_month", team_id=None):
        """
        Sales rep leaderboard: ranked by closed revenue, deal count, activity count.
        """
        start_date, end_date = cls.get_date_range(date_range)

        reps = User.objects.filter(
            role__in=[User.Role.SALES_REP, User.Role.SALES_MANAGER],
            is_active=True,
        )

        if team_id:
            reps = reps.filter(team_id=team_id)

        leaderboard = []
        for rep in reps:
            won_deals = Deal.objects.filter(
                owner=rep,
                stage__is_won=True,
                actual_close_date__range=(start_date, end_date),
            )
            open_deals = Deal.objects.filter(
                owner=rep,
            ).exclude(Q(stage__is_won=True) | Q(stage__is_lost=True))

            activities = ActivityLog.objects.filter(
                user=rep,
                created_at__date__range=(start_date, end_date),
            ).count()

            leaderboard.append(
                {
                    "user_id": str(rep.id),
                    "name": rep.get_full_name(),
                    "team": rep.team.name if rep.team else None,
                    "won_deals": won_deals.count(),
                    "won_revenue": float(
                        won_deals.aggregate(total=Sum("value")).get("total") or 0
                    ),
                    "open_deals": open_deals.count(),
                    "open_pipeline_value": float(
                        open_deals.aggregate(total=Sum("value")).get("total") or 0
                    ),
                    "activities": activities,
                }
            )

        # Sort by won revenue descending
        leaderboard.sort(key=lambda x: x["won_revenue"], reverse=True)

        return {"leaderboard": leaderboard, "period": {"start": str(start_date), "end": str(end_date)}}

    @classmethod
    def conversion_analytics(cls, pipeline_id=None, date_range="last_90_days"):
        """
        Stage-to-stage conversion rates.
        """
        start_date, end_date = cls.get_date_range(date_range)

        if pipeline_id:
            pipeline = Pipeline.objects.get(id=pipeline_id)
        else:
            pipeline = Pipeline.objects.filter(is_default=True).first() or Pipeline.objects.first()

        if not pipeline:
            return {"conversions": []}

        stages = list(pipeline.stages.order_by("order"))
        conversions = []

        for i in range(len(stages) - 1):
            current_stage = stages[i]
            next_stage = stages[i + 1]

            current_count = Deal.objects.filter(stage=current_stage).count()
            # Count deals that made it past this stage
            advanced_count = Deal.objects.filter(
                stage__pipeline=pipeline,
                stage__order__gte=next_stage.order,
            ).count()

            rate = (advanced_count / current_count * 100) if current_count > 0 else 0

            conversions.append(
                {
                    "from_stage": current_stage.name,
                    "to_stage": next_stage.name,
                    "from_count": current_count,
                    "to_count": advanced_count,
                    "conversion_rate": round(rate, 2),
                }
            )

        return {
            "pipeline": pipeline.name,
            "conversions": conversions,
        }
