from rest_framework import viewsets, permissions
from django.db.models import Q
from datetime import timedelta

from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Block, Flashcard, ReviewLog
from .serializers import BlockSerializer, FlashcardSerializer, ReviewLogSerializer,FolderSerializer,Folder,DocumentSerializer
from rest_framework import viewsets, permissions, status,generics   
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Block, Flashcard, ReviewLog,Document


from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from django.db.models import Count, Min
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.utils import timezone as dj_tz
from zoneinfo import ZoneInfo
from datetime import datetime, time, timedelta, timezone as dt_timezone
from django.db.models.functions import TruncDate
from django.db.models import Count, Min

class OwnerQuerysetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(owner=self.request.user)
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class FolderViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Folder.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        parent_id = self.request.query_params.get("parent")
        if parent_id is not None:
            qs = qs.filter(parent_id=parent_id)
        return qs.order_by("created_at", "id")
    
    @extend_schema(tags=["Folders"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    

class DocumentViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Document.objects.select_related("folder")

    def get_queryset(self):
        qs = super().get_queryset()
        folder_id = self.request.query_params.get("folder")
        if folder_id:
            qs = qs.filter(folder_id=folder_id)
        search = self.request.query_params.get("q")
        if search:
            qs = qs.filter(Q(title__icontains=search))
        # return qs
        return qs.order_by("created_at", "id")

    @extend_schema(
        tags=["Documents"],
        parameters=[
            OpenApiParameter(name="folder", description="ID de carpeta para filtrar", required=False, type=int),
            OpenApiParameter(name="q", description="Búsqueda por título", required=False, type=str),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class BlockViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = BlockSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Block.objects.select_related("document")

    def get_queryset(self):
        qs = super().get_queryset().filter(document__owner=self.request.user)
        doc_id = self.request.query_params.get("document")
        if doc_id:
            qs = qs.filter(document_id=doc_id)
        return qs

class FlashcardViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = FlashcardSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Flashcard.objects.select_related("document", "block")

    def get_queryset(self):
        qs = super().get_queryset().filter(owner=self.request.user)
        doc_id = self.request.query_params.get("document")
        if doc_id:
            qs = qs.filter(document_id=doc_id)
        before = self.request.query_params.get("before")
        if before:
            # si te llaman /flashcards/?before=ISO, también sirve como filtro simple
            try:
                cutoff = timezone.datetime.fromisoformat(before)
                if timezone.is_naive(cutoff):
                    cutoff = timezone.make_aware(cutoff, timezone.get_current_timezone())
                qs = qs.filter(next_review__lte=cutoff)
            except Exception:
                pass
        return qs

    @extend_schema(
        request=None,
        responses=FlashcardSerializer(many=True),
        parameters=[OpenApiParameter(name="before", description="ISO datetime; next_review <= before", required=False, type=str)],
        tags=["Study"],
    )
    @action(detail=False, methods=["GET"], url_path="due")
    def due(self, request):
        before = request.query_params.get("before")
        now = timezone.now()
        cutoff = now
        if before:
            try:
                cutoff = timezone.datetime.fromisoformat(before)
                if timezone.is_naive(cutoff):
                    cutoff = timezone.make_aware(cutoff, timezone.get_current_timezone())
            except Exception:
                pass
        qs = self.get_queryset().filter(next_review__lte=cutoff)
        page = self.paginate_queryset(qs)
        ser = self.get_serializer(page or qs, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @extend_schema(
        tags=["Study"],
        request={"type": "object", "properties": {"grade": {"type": "string", "enum": ["again","hard","good","easy"]}, "duration_ms": {"type": "integer"}}},
        responses=FlashcardSerializer,
    )
    # @action(detail=True, methods=["POST"], url_path="review")
    # def review(self, request, pk=None):
    #     """Scheduler básico: ajusta next_review y guarda ReviewLog."""
    #     card: Flashcard = self.get_object()
    #     grade = request.data.get("grade")
    #     duration_ms = int(request.data.get("duration_ms") or 0)

    #     add_days = {"again": 0, "hard": 1, "good": 3, "easy": 5}.get(grade, 1)
    #     next_rev = timezone.now() + timezone.timedelta(days=add_days)
    #     card.next_review = next_rev
    #     card.review_count = (card.review_count or 0) + 1
    #     card.owner = request.user  # por si acaso
    #     card.save(update_fields=["next_review", "review_count", "owner", "updated_at"])

    #     ReviewLog.objects.create(
    #         owner=request.user,
    #         flashcard=card,
    #         grade=grade,
    #         interval_days=add_days,
    #         next_review=next_rev,
    #         duration_ms=duration_ms,
    #     )
    #     return Response(self.get_serializer(card).data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    # @action(detail=True, methods=["POST"], url_path="review")
    # def review(self, request, pk=None):
    #     """
    #     Guarda el review del usuario y agenda la próxima revisión.
    #     Body: { "grade": "again|hard|good|easy", "duration_ms": 1234 }
    #     """
    #     card: Flashcard = self.get_object()
    #     grade = request.data.get("grade")
    #     duration_ms = int(request.data.get("duration_ms") or 0)

    #     if grade not in ("again", "hard", "good", "easy"):
    #         return Response({"detail": "Invalid grade"}, status=status.HTTP_400_BAD_REQUEST)

    #     # Scheduler MUY básico (ajústalo luego a tu algoritmo SR preferido)
    #     add_days_map = {"again": 0, "hard": 1, "good": 3, "easy": 5}
    #     add_days = add_days_map[grade]
    #     next_rev = timezone.now() + timezone.timedelta(days=add_days)

    #     card.next_review = next_rev
    #     card.review_count = (card.review_count or 0) + 1
    #     card.owner = request.user  # por si acaso
    #     card.save(update_fields=["next_review", "review_count", "owner", "updated_at"])

    #     ReviewLog.objects.create(
    #         owner=request.user,
    #         flashcard=card,
    #         grade=grade,
    #         interval_days=add_days,
    #         next_review=next_rev,
    #         duration_ms=duration_ms,
    #     )

    #     serializer = self.get_serializer(card)
    #     return Response(serializer.data, status=status.HTTP_200_OK)
    @action(detail=True, methods=["POST"], url_path="review")
    # def review(self, request, pk=None):
    #     card: Flashcard = self.get_object()
    #     grade = request.data.get("grade")
    #     duration_ms = int(request.data.get("duration_ms") or 0)

    #     # acepta también skip
    #     if grade not in ("again", "hard", "good", "easy", "skip"):
    #         return Response({"detail": "Invalid grade"}, status=status.HTTP_400_BAD_REQUEST)

    #     from django.utils import timezone
    #     delta_map = {
    #         "again": timezone.timedelta(minutes=1),   # olvidé
    #         "hard":  timezone.timedelta(hours=12),    # parcial
    #         "good":  timezone.timedelta(hours=24),    # con esfuerzo
    #         "easy":  timezone.timedelta(days=4),      # fácil
    #         "skip":  timezone.timedelta(hours=1),     # saltar
    #     }
    #     delta = delta_map[grade]
    #     next_rev = timezone.now() + delta

    #     card.next_review = next_rev
    #     if grade != "skip":  # saltar NO incrementa conteo
    #         card.review_count = (card.review_count or 0) + 1
    #     card.owner = request.user
    #     card.save(update_fields=["next_review", "review_count", "owner", "updated_at"])

    #     ReviewLog.objects.create(
    #         owner=request.user,
    #         flashcard=card,
    #         grade=grade,
    #         interval_days=delta.days,  # seguirá 0 para min/horas; está bien
    #         next_review=next_rev,
    #         duration_ms=duration_ms,
    #     )
    #     return Response(FlashcardSerializer(card).data, status=status.HTTP_200_OK)


    # def review(self, request, pk=None):
    #     print(f"[REVIEW] user={request.user.id} pk={pk} body={request.data}")
    #     card: Flashcard = self.get_object()
    #     print(f"[REVIEW] current card: id={card.id} difficulty={card.difficulty} next_review={card.next_review}")
    #     card = self.get_object()
    #     grade = request.data.get("grade")  # 'again' | 'hard' | 'good' | 'easy' | 'skip'
    #     manual_minutes = request.data.get("manualIntervalMinutes")

    #     now = timezone.now()

    #     # 1) Intervalo (respetamos manual si viene)
    #     if manual_minutes is not None:
    #         try:
    #             manual_minutes = int(manual_minutes)
    #             print(f"[REVIEW] usando intervalo MANUAL: {manual_minutes} min → next_review={next_review.isoformat()}")
    #         except (TypeError, ValueError):
    #             manual_minutes = None

    #     if manual_minutes is not None:
    #         next_review = now + timedelta(minutes=manual_minutes)
    #     else:
    #         # valores por defecto (ajústalos a tu gusto)
    #         if grade == "again":
    #             next_review = now + timedelta(minutes=1)
    #         elif grade == "hard":
    #             next_review = now + timedelta(hours=1)
    #         elif grade == "good":
    #             next_review = now + timedelta(days=1)
    #         elif grade == "easy":
    #             next_review = now + timedelta(days=2)
    #         elif grade == "skip":
    #             next_review = now + timedelta(hours=1)
    #         else:
    #             print(f"[REVIEW] grade inválido: {grade}")
    #             return Response({"detail": "grade inválido"}, status=status.HTTP_400_BAD_REQUEST)

    #         print(f"[REVIEW] usando intervalo POR DEFECTO para grade={grade} → next_review={next_review.isoformat()}")


    #     # 2) Mapeo de grade → difficulty (persistimos el último botón marcado)
    #     grade_to_difficulty = {
    #         "again": "repetir",
    #         "hard": "dificil",
    #         "good": "facil",
    #         "easy": "muy-facil",
    #         # "skip": no cambia difficulty
    #     }
    #     if grade != "skip":
    #         card.difficulty = grade_to_difficulty.get(grade, card.difficulty)
    #         card.review_count = (card.review_count or 0) + 1
    #         print(f"[REVIEW] difficulty: {old_diff} → {card.difficulty}; review_count={card.review_count} (+1)")

    #     card.next_review = next_review
    #     card.save(update_fields=["difficulty", "next_review", "review_count", "updated_at"])

    #     # (Opcional) log de la review
    #     # ReviewLog.objects.create(flashcard=card, grade=grade, scheduled_for=next_review, owner=request.user)

    #     print(f"[REVIEW] GUARDADO OK card_id={card.id} next_review={card.next_review} difficulty={card.difficulty}")


    #     from .serializers import FlashcardSerializer
    #     return Response(FlashcardSerializer(card).data, status=status.HTTP_200_OK)
    # def review(self, request, pk=None):
    #     card: Flashcard = self.get_object()

    #     grade = request.data.get("grade")  # 'again' | 'hard' | 'good' | 'easy' | 'skip'
    #     manual = request.data.get("manualIntervalMinutes")

    #     # Log de entrada
    #     print(f"[REVIEW] user={request.user.id} pk={pk} body={request.data}")
    #     print(f"[REVIEW] current card: id={card.id} difficulty={card.difficulty} next_review={card.next_review}")

    #     # Parse manual como int o None
    #     try:
    #         manual = int(manual) if manual not in (None, "", "null") else None
    #     except (TypeError, ValueError):
    #         manual = None

    #     now = timezone.now()

    #     if manual is not None:
    #         next_review = now + timedelta(minutes=manual)
    #         print(f"[REVIEW] usando intervalo MANUAL: {manual} min → next_review={next_review.isoformat()}")
    #     else:
    #         delta_map = {
    #             "again": timedelta(minutes=1),   # Olvidé (1m)
    #             "hard":  timedelta(hours=12),    # Parcial (12h)
    #             "good":  timedelta(hours=24),    # Con esfuerzo (24h)
    #             "easy":  timedelta(days=4),      # Fácil (4 días)
    #             "skip":  timedelta(hours=1),     # Saltar (1h)
    #         }
    #         delta = delta_map.get(grade)
    #         if not delta:
    #             print(f"[REVIEW] grade inválido: {grade}")
    #             return Response({"detail": "grade inválido"}, status=status.HTTP_400_BAD_REQUEST)
    #         next_review = now + delta
    #         print(f"[REVIEW] usando intervalo DEFAULT para grade={grade} → next_review={next_review.isoformat()}")

    #     # Persistimos difficulty sólo si NO es skip
    #     if grade != "skip":
    #         grade_to_difficulty = {
    #             "again": "repetir",
    #             "hard": "dificil",
    #             "good": "facil",
    #             "easy": "muy-facil",
    #         }
    #         old_diff = card.difficulty
    #         card.difficulty = grade_to_difficulty.get(grade, card.difficulty)
    #         card.review_count = (card.review_count or 0) + 1
    #         print(f"[REVIEW] difficulty: {old_diff} → {card.difficulty}; review_count={card.review_count}")
    #     else:
    #         print("[REVIEW] skip: no cambia difficulty ni review_count")

    #     card.next_review = next_review
    #     card.save(update_fields=["difficulty", "next_review", "review_count", "updated_at"])

    #     print(f"[REVIEW] GUARDADO OK card_id={card.id} next_review={card.next_review} difficulty={card.difficulty}")

    #     return Response(FlashcardSerializer(card).data, status=status.HTTP_200_OK)
    def review(self, request, pk=None):
        card = self.get_object()
        grade = request.data.get("grade")  # 'again' | 'hard' | 'good' | 'easy' | 'skip'
        manual_minutes = request.data.get("manualIntervalMinutes")

        now = timezone.now()
        print(f"[REVIEW] user={request.user.id} pk={pk} body={request.data}")
        print(f"[REVIEW] current card: id={card.id} difficulty={card.difficulty} next_review={card.next_review}")

        # 1) Intervalo
        if manual_minutes is not None:
            try:
                manual_minutes = int(manual_minutes)
            except (TypeError, ValueError):
                manual_minutes = None

        if manual_minutes is not None:
            next_review = now + timedelta(minutes=manual_minutes)
            print(f"[REVIEW] usando intervalo MANUAL: {manual_minutes} min → next_review={next_review.isoformat()}")
        else:
            if grade == "again":
                next_review = now + timedelta(minutes=1)
            elif grade == "hard":
                next_review = now + timedelta(hours=12)  # si así lo quieres por defecto
            elif grade == "good":
                next_review = now + timedelta(hours=24)
            elif grade == "easy":
                next_review = now + timedelta(days=4)
            elif grade == "skip":
                next_review = now + timedelta(hours=1)
            else:
                return Response({"detail": "grade inválido"}, status=status.HTTP_400_BAD_REQUEST)
            print(f"[REVIEW] usando intervalo AUTO por grade='{grade}' → next_review={next_review.isoformat()}")

        # 2) Persistir difficulty acorde al grade (excepto skip)
        grade_to_difficulty = {
            "again": "olvide",
            "hard": "parcialmente",
            "good": "esfuerzo",
            "easy": "facil",
            "skip": "saltar"
        }

        new_diff = grade_to_difficulty.get(grade, card.difficulty)
        card.difficulty = new_diff

        # No sumar review_count en skip
        if grade != "skip":
            card.review_count = (card.review_count or 0) + 1
        # if grade != "skip":
        #     card.difficulty = grade_to_difficulty.get(grade, card.difficulty)
        #     card.review_count = (card.review_count or 0) + 1

        card.next_review = next_review
        card.save(update_fields=["difficulty", "next_review", "review_count", "updated_at"])

        print(f"[REVIEW] saved: id={card.id} difficulty={card.difficulty} next_review={card.next_review} reviews={card.review_count}")

        return Response(FlashcardSerializer(card).data, status=status.HTTP_200_OK)
    
class ReviewLogViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ReviewLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ReviewLog.objects.select_related("flashcard")

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)
    



# class DashboardSummaryView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         USE_TZ = bool(getattr(settings, "USE_TZ", True))
#         # Si no quieres pasar tz desde el front, tomamos settings.TIME_ZONE (o Lima por defecto)
#         default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
#         tzname = request.query_params.get("tz") or default_tzname

#         try:
#             tz = ZoneInfo(tzname)
#         except Exception:
#             tz = ZoneInfo(default_tzname)

#         # ===== tiempos base según USE_TZ =====
#         if USE_TZ:
#             now_utc = dj_tz.now()  # aware en UTC
#             now_local = now_utc.astimezone(tz)
#             today_local = now_local.date()

#             # Ventanas “hoy” en LOCAL, convertidas a UTC para filtrar en DB (DB guarda UTC cuando USE_TZ=True)
#             start_today_local = datetime.combine(today_local, time.min, tzinfo=tz)
#             end_today_local = start_today_local + timedelta(days=1)

#             start_today_filter = start_today_local.astimezone(dt_timezone.utc)
#             end_today_filter = end_today_local.astimezone(dt_timezone.utc)
#             now_for_overdue = now_utc  # aware UTC

#             # Últimos 7 días
#             start7_local_date = today_local - timedelta(days=6)
#             start7_local = datetime.combine(start7_local_date, time.min, tzinfo=tz)
#             start7_filter = start7_local.astimezone(dt_timezone.utc)

#             trunc_expr = TruncDate("created_at", tzinfo=tz)  # agrupa por día LOCAL
#         else:
#             # Todo en naive local (tu setting TIME_ZONE=America/Lima ya hace que los auto_now* se guarden en Lima)
#             now_local = datetime.now()
#             today_local = now_local.date()

#             start_today_filter = datetime.combine(today_local, time.min)  # naive
#             end_today_filter = start_today_filter + timedelta(days=1)
#             now_for_overdue = now_local  # naive

#             start7_local_date = today_local - timedelta(days=6)
#             start7_filter = datetime.combine(start7_local_date, time.min)  # naive

#             trunc_expr = TruncDate("created_at")  # sin tzinfo

#         # ===== totales =====
#         total_folders = Folder.objects.filter(owner=user).count()
#         total_documents = Document.objects.filter(owner=user).count()
#         total_flashcards = Flashcard.objects.filter(owner=user).count()

#         # ===== due / today =====
#         due_overdue = Flashcard.objects.filter(
#             owner=user, next_review__isnull=False, next_review__lte=now_for_overdue
#         ).count()

#         due_today = Flashcard.objects.filter(
#             owner=user,
#             next_review__gte=start_today_filter,
#             next_review__lt=end_today_filter,
#         ).count()

#         # ===== por dificultad =====
#         diff_counts = (
#             Flashcard.objects.filter(owner=user)
#             .values("difficulty")
#             .annotate(count=Count("id"))
#         )
#         by_difficulty = {row["difficulty"] or "": row["count"] for row in diff_counts}
#         for k in ["olvide", "parcialmente", "esfuerzo", "facil", "saltar"]:
#             by_difficulty.setdefault(k, 0)

#         # ===== documentos recientes =====
#         recent_qs = (
#             Document.objects.filter(owner=user)
#             .annotate(
#                 flashcards_count=Count("flashcards", distinct=True),
#                 next_due=Min("flashcards__next_review"),
#             )
#             .order_by("-updated_at")[:12]
#             .values(
#                 "id", "title", "created_at", "updated_at",
#                 "flashcards_count", "next_due", "folder_id"
#             )
#         )
#         recent_docs = []
#         for d in recent_qs:
#             created_at = d["created_at"]
#             updated_at = d["updated_at"]
#             next_due = d["next_due"]
#             out = dict(d)

#             if USE_TZ:
#                 out["created_at_local"] = created_at.astimezone(tz).isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.astimezone(tz).isoformat() if updated_at else None
#                 out["next_due_local"] = next_due.astimezone(tz).isoformat() if next_due else None
#             else:
#                 # Son naive (Lima). Devuélvelos tal cual.
#                 out["created_at_local"] = created_at.isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.isoformat() if updated_at else None
#                 out["next_due_local"] = next_due.isoformat() if next_due else None

#             recent_docs.append(out)

#         # ===== reviews últimos 7 días (por día local si USE_TZ=True, sino por fecha naive) =====
#         reviews_7d = (
#             ReviewLog.objects.filter(owner=user, created_at__gte=start7_filter)
#             .annotate(d=trunc_expr)
#             .values("d")
#             .annotate(count=Count("id"))
#             .order_by("d")
#         )
#         bucket = {row["d"]: row["count"] for row in reviews_7d}

#         last7 = []
#         for i in range(7):
#             day = start7_local_date + timedelta(days=i)
#             last7.append({"date": day.isoformat(), "count": bucket.get(day, 0)})

#         # ===== streak =====
#         days_with_review = set(
#             ReviewLog.objects.filter(owner=user)
#             .annotate(d=trunc_expr)
#             .values_list("d", flat=True)
#         )
#         streak = 0
#         cursor = today_local
#         while cursor in days_with_review:
#             streak += 1
#             cursor = cursor - timedelta(days=1)

#         return Response({
#             "tz": tz.key,
#             "now_local": (now_local.isoformat() if USE_TZ else now_local.isoformat()),
#             "totals": {
#                 "folders": total_folders,
#                 "documents": total_documents,
#                 "flashcards": total_flashcards,
#             },
#             "due": {"overdue": due_overdue, "today": due_today},
#             "by_difficulty": by_difficulty,
#             "recent_documents": recent_docs,
#             "reviews_last_7d": last7,
#             "streak": streak,
#         })


# class DashboardSummaryView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         USE_TZ = bool(getattr(settings, "USE_TZ", True))
#         default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
#         tzname = request.query_params.get("tz") or default_tzname

#         try:
#             tz = ZoneInfo(tzname)
#         except Exception:
#             tz = ZoneInfo(default_tzname)

#         # ===== tiempos base según USE_TZ =====
#         if USE_TZ:
#             now_utc = dj_tz.now()              # aware UTC
#             now_local = now_utc.astimezone(tz) # aware local
#             today_local = now_local.date()

#             # Ventana "hoy" local -> filtrar en DB con UTC
#             start_today_local = datetime.combine(today_local, time.min, tzinfo=tz)
#             end_today_local = start_today_local + timedelta(days=1)
#             start_today_filter = start_today_local.astimezone(dt_timezone.utc)
#             end_today_filter = end_today_local.astimezone(dt_timezone.utc)

#             now_for_overdue = now_utc          # para pendientes ahora
#             # Últimos 7 días (incluye hoy)
#             start7_local_date = today_local - timedelta(days=6)
#             start7_local = datetime.combine(start7_local_date, time.min, tzinfo=tz)
#             start7_filter = start7_local.astimezone(dt_timezone.utc)

#             trunc_expr = TruncDate("created_at", tzinfo=tz)
#         else:
#             # Todo naive en hora local (ej. Lima)
#             now_local = datetime.now()
#             today_local = now_local.date()

#             start_today_filter = datetime.combine(today_local, time.min)
#             end_today_filter = start_today_filter + timedelta(days=1)
#             now_for_overdue = now_local

#             start7_local_date = today_local - timedelta(days=6)
#             start7_filter = datetime.combine(start7_local_date, time.min)

#             trunc_expr = TruncDate("created_at")

#         # ===== totales =====
#         total_folders = Folder.objects.filter(owner=user).count()
#         total_documents = Document.objects.filter(owner=user).count()
#         total_flashcards = Flashcard.objects.filter(owner=user).count()

#         # ===== pendientes =====
#         # ahora (vencidas + tocan ya)
#         due_overdue = Flashcard.objects.filter(
#             owner=user, next_review__isnull=False, next_review__lte=now_for_overdue
#         ).count()

#         # hoy (00:00–24:00 local)
#         due_today = Flashcard.objects.filter(
#             owner=user,
#             next_review__gte=start_today_filter,
#             next_review__lt=end_today_filter,
#         ).count()

#         # ===== por dificultad =====
#         diff_counts = (
#             Flashcard.objects.filter(owner=user)
#             .values("difficulty")
#             .annotate(count=Count("id"))
#         )
#         by_difficulty = {row["difficulty"] or "": row["count"] for row in diff_counts}
#         for k in ["olvide", "parcialmente", "esfuerzo", "facil", "saltar"]:
#             by_difficulty.setdefault(k, 0)

#         # ===== documentos recientes =====
#         recent_qs = (
#             Document.objects.filter(owner=user)
#             .annotate(
#                 flashcards_count=Count("flashcards", distinct=True),
#                 next_due=Min("flashcards__next_review"),
#             )
#             .order_by("-updated_at")[:12]
#             .values(
#                 "id", "title", "created_at", "updated_at",
#                 "flashcards_count", "next_due", "folder_id"
#             )
#         )
#         recent_docs = []
#         for d in recent_qs:
#             created_at = d["created_at"]
#             updated_at = d["updated_at"]
#             next_due = d["next_due"]
#             out = dict(d)

#             if USE_TZ:
#                 out["created_at_local"] = created_at.astimezone(tz).isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.astimezone(tz).isoformat() if updated_at else None
#                 out["next_due_local"] = next_due.astimezone(tz).isoformat() if next_due else None
#             else:
#                 out["created_at_local"] = created_at.isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.isoformat() if updated_at else None
#                 out["next_due_local"] = next_due.isoformat() if next_due else None

#             recent_docs.append(out)

#         # ===== reviews HOY (para completadas/accuracy) =====
#         reviews_today = ReviewLog.objects.filter(
#             owner=user,
#             created_at__gte=start_today_filter,
#             created_at__lt=end_today_filter,
#         ).exclude(grade=ReviewLog.SKIP)

#         completed_today = (
#             reviews_today.values("flashcard").distinct().count()
#         )

#         acc_den = reviews_today.count()
#         acc_num = reviews_today.filter(
#             grade__in=[ReviewLog.GOOD, ReviewLog.EASY]
#         ).count()

#         # Fallback a últimos 7 días si hoy no hay intentos
#         if acc_den == 0:
#             reviews_7d_for_acc = ReviewLog.objects.filter(
#                 owner=user,
#                 created_at__gte=start7_filter,
#             ).exclude(grade=ReviewLog.SKIP)
#             acc_den = reviews_7d_for_acc.count()
#             acc_num = reviews_7d_for_acc.filter(
#                 grade__in=[ReviewLog.GOOD, ReviewLog.EASY]
#             ).count()

#         accuracy_pct = (acc_num * 100.0 / acc_den) if acc_den else 0.0

#         # ===== temas (hoy y ahora) =====
#         themes_qs = (
#             Flashcard.objects.filter(owner=user)
#             .exclude(Q(theme__isnull=True) | Q(theme=""))
#             .values("theme")
#             .annotate(
#                 total=Count("id"),
#                 pending_today=Count(
#                     "id",
#                     filter=Q(next_review__gte=start_today_filter,
#                              next_review__lt=end_today_filter),
#                 ),
#                 pending_now=Count(
#                     "id",
#                     filter=Q(next_review__isnull=False, next_review__lte=now_for_overdue),
#                 ),
#             )
#             .order_by("-pending_now", "-pending_today", "-total")[:24]
#         )
#         themes_list = list(themes_qs)

#         # ===== reviews últimos 7 días (para gráfico) =====
#         reviews_7d = (
#             ReviewLog.objects.filter(owner=user, created_at__gte=start7_filter)
#             .annotate(d=trunc_expr)
#             .values("d")
#             .annotate(count=Count("id"))
#             .order_by("d")
#         )
#         bucket = {row["d"]: row["count"] for row in reviews_7d}

#         last7 = []
#         for i in range(7):
#             day = start7_local_date + timedelta(days=i)
#             last7.append({"date": day.isoformat(), "count": bucket.get(day, 0)})

#         # ===== racha (no cuenta skip) =====
#         days_with_review = set(
#             ReviewLog.objects.filter(owner=user)
#             .exclude(grade=ReviewLog.SKIP)
#             .annotate(d=trunc_expr)
#             .values_list("d", flat=True)
#         )
#         streak = 0
#         cursor = today_local
#         while cursor in days_with_review:
#             streak += 1
#             cursor = cursor - timedelta(days=1)

#         # ===== today-block (lo que pinta tu UI) =====
#         today_block = {
#             # IMPORTANTE: haces que la primera cajita y el botón muestren el mismo número:
#             # "pending": due_overdue,           # pendientes AHORA (no solo hoy)
#             "pending": due_today,           # pendientes AHORA (no solo hoy)
#             "completed": completed_today,     # flashcards distintas revisadas hoy (sin skip)
#             "new_cards": total_flashcards,    # como pediste: todas las flashcards del usuario
#             "accuracy_pct": round(accuracy_pct, 1),
#         }

#         return Response({
#             "tz": tz.key,
#             "now_local": now_local.isoformat(),
#             "totals": {
#                 "folders": total_folders,
#                 "documents": total_documents,
#                 "flashcards": total_flashcards,
#             },
#             "today": today_block,
#             "due": {"overdue": due_overdue, "today": due_today},
#             "by_difficulty": by_difficulty,
#             "themes": themes_list,
#             "recent_documents": recent_docs,
#             "reviews_last_7d": last7,
#             "streak": streak,
#         })


# class DashboardSummaryView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         # ===== TZ =====
#         USE_TZ = bool(getattr(settings, "USE_TZ", True))
#         default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
#         tzname = request.query_params.get("tz") or default_tzname
#         try:
#             tz = ZoneInfo(tzname)
#         except Exception:
#             tz = ZoneInfo(default_tzname)

#         # ===== tiempos base según USE_TZ =====
#         if USE_TZ:
#             now_utc = dj_tz.now()                 # aware en UTC
#             now_local = now_utc.astimezone(tz)    # aware en zona local
#             today_local = now_local.date()

#             # ventana "hoy" local -> se filtra en DB usando UTC
#             start_today_local = datetime.combine(today_local, time.min, tzinfo=tz)
#             end_today_local   = start_today_local + timedelta(days=1)
#             start_today_filter = start_today_local.astimezone(dt_timezone.utc)
#             end_today_filter   = end_today_local.astimezone(dt_timezone.utc)

#             now_for_overdue = now_utc  # para "vencidas / ahora"

#             # últimos 7 días (incluye hoy) en local -> a UTC para filtrar
#             start7_local_date = today_local - timedelta(days=6)
#             start7_local = datetime.combine(start7_local_date, time.min, tzinfo=tz)
#             start7_filter = start7_local.astimezone(dt_timezone.utc)

#             trunc_expr = TruncDate("created_at", tzinfo=tz)
#         else:
#             # Todo naive en hora local (p. ej. Lima). Los auto_now* se guardan en local.
#             now_local = datetime.now()
#             today_local = now_local.date()

#             start_today_filter = datetime.combine(today_local, time.min)
#             end_today_filter   = start_today_filter + timedelta(days=1)
#             now_for_overdue    = now_local

#             start7_local_date = today_local - timedelta(days=6)
#             start7_filter = datetime.combine(start7_local_date, time.min)

#             trunc_expr = TruncDate("created_at")

#         # ===== totales =====
#         total_folders   = Folder.objects.filter(owner=user).count()
#         total_documents = Document.objects.filter(owner=user).count()
#         total_flashcards = Flashcard.objects.filter(owner=user).count()

#         # ===== pendientes =====
#         # AHORA (vencidas a este instante)
#         due_overdue = Flashcard.objects.filter(
#             owner=user, next_review__isnull=False, next_review__lte=now_for_overdue
#         ).count()

#         # HOY (00:00–24:00 local)
#         due_today = Flashcard.objects.filter(
#             owner=user,
#             next_review__gte=start_today_filter,
#             next_review__lt=end_today_filter,
#         ).count()

#         # ===== por dificultad =====
#         diff_counts = (
#             Flashcard.objects.filter(owner=user)
#             .values("difficulty")
#             .annotate(count=Count("id"))
#         )
#         by_difficulty = {row["difficulty"] or "": row["count"] for row in diff_counts}
#         for k in ["olvide", "parcialmente", "esfuerzo", "facil", "saltar"]:
#             by_difficulty.setdefault(k, 0)

#         # ===== documentos recientes + métricas =====
#         recent_qs = (
#             Document.objects.filter(owner=user)
#             .annotate(
#                 flashcards_count=Count("flashcards", distinct=True),
#                 next_due=Min("flashcards__next_review"),
#             )
#             .order_by("-updated_at")[:12]
#             .values(
#                 "id", "title", "created_at", "updated_at",
#                 "flashcards_count", "next_due", "folder_id"
#             )
#         )
#         recent_docs = []
#         for d in recent_qs:
#             created_at = d["created_at"]
#             updated_at = d["updated_at"]
#             next_due   = d["next_due"]
#             out = dict(d)

#             if USE_TZ:
#                 out["created_at_local"] = created_at.astimezone(tz).isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.astimezone(tz).isoformat() if updated_at else None
#                 out["next_due_local"]   = next_due.astimezone(tz).isoformat()   if next_due else None
#             else:
#                 out["created_at_local"] = created_at.isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.isoformat() if updated_at else None
#                 out["next_due_local"]   = next_due.isoformat()   if next_due else None

#             recent_docs.append(out)

#         # ===== reviews HOY (para completadas/precision) =====
#         # Etiquetas que usas: "olvide", "parcialmente", "esfuerzo", "facil", "saltar"
#         SKIP = "saltar"
#         OK_GRADES = ("esfuerzo", "facil")

#         reviews_today_all = ReviewLog.objects.filter(
#             owner=user,
#             created_at__gte=start_today_filter,
#             created_at__lt=end_today_filter,
#         )

#         # COMPLETADAS: fc que hoy NO tienen "saltar" y sí tienen algún review no-skip
#         skip_fc_today = reviews_today_all.filter(grade=SKIP)\
#             .values_list("flashcard", flat=True).distinct()

#         completed_today = reviews_today_all.exclude(grade=SKIP)\
#             .exclude(flashcard__in=skip_fc_today)\
#             .values("flashcard").distinct().count()

#         # PRECISIÓN: (correctas / intentos) excluyendo "saltar"
#         reviews_today_for_acc = reviews_today_all.exclude(grade=SKIP)
#         acc_den = reviews_today_for_acc.count()
#         acc_num = reviews_today_for_acc.filter(grade__in=OK_GRADES).count()

#         # Fallback a últimos 7 días si hoy no hay intentos
#         if acc_den == 0:
#             reviews_7d_for_acc = ReviewLog.objects.filter(
#                 owner=user,
#                 created_at__gte=start7_filter,
#             ).exclude(grade=SKIP)
#             acc_den = reviews_7d_for_acc.count()
#             acc_num = reviews_7d_for_acc.filter(grade__in=OK_GRADES).count()

#         accuracy_pct = (acc_num * 100.0 / acc_den) if acc_den else 0.0

#         # ===== temas (hoy y ahora) =====
#         themes_qs = (
#             Flashcard.objects.filter(owner=user)
#             .exclude(Q(theme__isnull=True) | Q(theme=""))
#             .values("theme")
#             .annotate(
#                 total=Count("id"),
#                 pending_today=Count(
#                     "id",
#                     filter=Q(next_review__gte=start_today_filter,
#                              next_review__lt=end_today_filter),
#                 ),
#                 pending_now=Count(
#                     "id",
#                     filter=Q(next_review__isnull=False, next_review__lte=now_for_overdue),
#                 ),
#             )
#             .order_by("-pending_today", "-pending_now", "-total")[:24]
#         )
#         themes_list = list(themes_qs)

#         # ===== reviews últimos 7 días (gráfico) =====
#         reviews_7d = (
#             ReviewLog.objects.filter(owner=user, created_at__gte=start7_filter)
#             .annotate(d=trunc_expr)
#             .values("d")
#             .annotate(count=Count("id"))
#             .order_by("d")
#         )
#         bucket = {row["d"]: row["count"] for row in reviews_7d}

#         last7 = []
#         for i in range(7):
#             day = start7_local_date + timedelta(days=i)
#             last7.append({"date": day.isoformat(), "count": bucket.get(day, 0)})

#         # ===== racha (no cuenta "saltar") =====
#         days_with_review = set(
#             ReviewLog.objects.filter(owner=user)
#             .exclude(grade=SKIP)
#             .annotate(d=trunc_expr)
#             .values_list("d", flat=True)
#         )
#         streak = 0
#         cursor = today_local
#         while cursor in days_with_review:
#             streak += 1
#             cursor = cursor - timedelta(days=1)

#         # ===== bloque "hoy" para tu UI =====
#         today_block = {
#             "pending": due_today,                 # Pendientes HOY
#             "completed": completed_today,         # Distintas fc completadas hoy
#             "new_cards": total_flashcards,        # Total flashcards del usuario (como pediste)
#             "accuracy_pct": round(accuracy_pct, 1),
#         }

#         return Response({
#             "tz": tz.key,
#             "now_local": now_local.isoformat(),
#             "totals": {
#                 "folders": total_folders,
#                 "documents": total_documents,
#                 "flashcards": total_flashcards,
#             },
#             "today": today_block,
#             "due": {"overdue": due_overdue, "today": due_today},
#             "by_difficulty": by_difficulty,
#             "themes": themes_list,
#             "recent_documents": recent_docs,
#             "reviews_last_7d": last7,
#             "streak": streak,
#         })
    

# class FlashcardListView(generics.ListAPIView):
#     permission_classes = [permissions.IsAuthenticated]
#     serializer_class = FlashcardSerializer

#     def get_queryset(self):
#         user = self.request.user
#         qs = Flashcard.objects.filter(owner=user)

#         # filtros opcionales
#         theme = self.request.query_params.get("theme")
#         if theme:
#             qs = qs.filter(theme=theme)

#         folder = self.request.query_params.get("folder")
#         if folder:
#             qs = qs.filter(document__folder_id=folder)

#         due = self.request.query_params.get("due")
#         USE_TZ = bool(getattr(settings, "USE_TZ", True))
#         default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
#         tzname = self.request.query_params.get("tz") or default_tzname
#         try:
#             tz = ZoneInfo(tzname)
#         except Exception:
#             tz = ZoneInfo(default_tzname)

#         if USE_TZ:
#             now_utc = dj_tz.now()
#             now_local = now_utc.astimezone(tz)
#             today_local = now_local.date()

#             start_today_local = datetime.combine(today_local, time.min, tzinfo=tz)
#             end_today_local   = start_today_local + timedelta(days=1)
#             start_today_utc   = start_today_local.astimezone(dt_timezone.utc)
#             end_today_utc     = end_today_local.astimezone(dt_timezone.utc)

#             if due == "now":
#                 qs = qs.filter(next_review__isnull=False, next_review__lte=now_utc)
#             elif due == "today":
#                 qs = qs.filter(next_review__gte=start_today_utc, next_review__lt=end_today_utc)
#         else:
#             now_local = datetime.now()
#             today_local = now_local.date()
#             start_today = datetime.combine(today_local, time.min)
#             end_today   = start_today + timedelta(days=1)

#             if due == "now":
#                 qs = qs.filter(next_review__isnull=False, next_review__lte=now_local)
#             elif due == "today":
#                 qs = qs.filter(next_review__gte=start_today, next_review__lt=end_today)

#         return qs.order_by("next_review", "id")


# def _grade_sets():
#     """
#     Construye sets robustos para filtrar por grade, soportando:
#     - Constantes del modelo (GOOD/EASY/SKIP) si existen (int/str)
#     - Strings equivalentes usados en tu app: "esfuerzo", "facil", "saltar"
#     - Strings en inglés por si tu modelo usa 'good', 'easy', 'skip'
#     """
#     values = []
#     for attr in ("SKIP", "GOOD", "EASY"):
#         if hasattr(ReviewLog, attr):
#             values.append(getattr(ReviewLog, attr))

#     SKIP_VALUES = set([v for v in values if v is not None and str(v).lower() in ["skip"]])
#     OK_VALUES   = set([v for v in values if v is not None and str(v).lower() in ["good", "easy"]])

#     # alias en español/inglés
#     SKIP_VALUES.update(["saltar", "skip"])
#     OK_VALUES.update(["facil", "esfuerzo", "easy", "good"])

#     return SKIP_VALUES, OK_VALUES


# class DashboardSummaryView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user

#         # ===== TZ =====
#         USE_TZ = bool(getattr(settings, "USE_TZ", True))
#         default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
#         tzname = request.query_params.get("tz") or default_tzname
#         try:
#             tz = ZoneInfo(tzname)
#         except Exception:
#             tz = ZoneInfo(default_tzname)

#         # ===== tiempos base según USE_TZ =====
#         if USE_TZ:
#             now_utc = dj_tz.now()                 # aware UTC
#             now_local = now_utc.astimezone(tz)    # aware local
#             today_local = now_local.date()

#             # ventana "hoy" local -> filtrar en DB con UTC (se usa abajo solo para 7d)
#             start_today_local  = datetime.combine(today_local, time.min, tzinfo=tz)
#             end_today_local    = start_today_local + timedelta(days=1)
#             start_today_filter = start_today_local.astimezone(dt_timezone.utc)
#             end_today_filter   = end_today_local.astimezone(dt_timezone.utc)

#             now_for_overdue   = now_utc

#             # últimos 7 días (incluye hoy) en local -> a UTC para filtrar
#             start7_local_date = today_local - timedelta(days=6)
#             start7_local      = datetime.combine(start7_local_date, time.min, tzinfo=tz)
#             start7_filter     = start7_local.astimezone(dt_timezone.utc)

#             trunc_expr = TruncDate("created_at", tzinfo=tz)
#         else:
#             now_local = datetime.now()
#             today_local = now_local.date()

#             start_today_filter = datetime.combine(today_local, time.min)
#             end_today_filter   = start_today_filter + timedelta(days=1)
#             now_for_overdue    = now_local

#             start7_local_date  = today_local - timedelta(days=6)
#             start7_filter      = datetime.combine(start7_local_date, time.min)

#             trunc_expr = TruncDate("created_at")

#         print("\n================= DASHBOARD DEBUG =================")
#         print(f"[user] id={getattr(user, 'id', None)}  username={getattr(user, 'username', None)}")
#         print(f"[tz] tzname={tz.key}  USE_TZ={USE_TZ}")
#         if USE_TZ:
#             print(f"[time] now_utc={now_utc}  now_local={now_local.isoformat()}")
#             print(f"[time] today_local={today_local}  start_today_utc={start_today_filter}  end_today_utc={end_today_filter}")
#             print(f"[time] start7_filter(UTC)={start7_filter}")
#         else:
#             print(f"[time] now_local={now_local.isoformat()}  today_local={today_local}")
#             print(f"[time] start_today={start_today_filter}  end_today={end_today_filter}")
#             print(f"[time] start7_filter(local)={start7_filter}")

#         # ===== totales =====
#         total_folders    = Folder.objects.filter(owner=user).count()
#         total_documents  = Document.objects.filter(owner=user).count()
#         total_flashcards = Flashcard.objects.filter(owner=user).count()
#         print(f"[totals] folders={total_folders} documents={total_documents} flashcards={total_flashcards}")

#         # ===== pendientes =====
#         # AHORA (vencidas a este instante)
#         due_overdue = Flashcard.objects.filter(
#             owner=user, next_review__isnull=False, next_review__lte=now_for_overdue
#         ).count()

#         # HOY (por fecha local robusta —> TruncDate evita problemas de UTC/local)
#         due_today = (
#             Flashcard.objects
#             .filter(owner=user)
#             .annotate(d=TruncDate("next_review", tzinfo=tz) if USE_TZ else TruncDate("next_review"))
#             .filter(d=today_local)
#             .count()
#         )
#         print(f"[due] overdue(now)={due_overdue}  today={due_today}")

#         # ===== por dificultad =====
#         diff_counts = (
#             Flashcard.objects.filter(owner=user)
#             .values("difficulty")
#             .annotate(count=Count("id"))
#         )
#         by_difficulty = {row["difficulty"] or "": row["count"] for row in diff_counts}
#         for k in ["olvide", "parcialmente", "esfuerzo", "facil", "saltar"]:
#             by_difficulty.setdefault(k, 0)
#         print(f"[by_difficulty] {by_difficulty}")

#         # ===== documentos recientes + métricas =====
#         recent_qs = (
#             Document.objects.filter(owner=user)
#             .annotate(
#                 flashcards_count=Count("flashcards", distinct=True),
#                 next_due=Min("flashcards__next_review"),
#             )
#             .order_by("-updated_at")[:12]
#             .values(
#                 "id", "title", "created_at", "updated_at",
#                 "flashcards_count", "next_due", "folder_id"
#             )
#         )
#         recent_docs = []
#         for d in recent_qs:
#             created_at = d["created_at"]
#             updated_at = d["updated_at"]
#             next_due   = d["next_due"]
#             out = dict(d)

#             if USE_TZ:
#                 out["created_at_local"] = created_at.astimezone(tz).isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.astimezone(tz).isoformat() if updated_at else None
#                 out["next_due_local"]   = next_due.astimezone(tz).isoformat()   if next_due else None
#             else:
#                 out["created_at_local"] = created_at.isoformat() if created_at else None
#                 out["updated_at_local"] = updated_at.isoformat() if updated_at else None
#                 out["next_due_local"]   = next_due.isoformat()   if next_due else None

#             recent_docs.append(out)
#         print(f"[recent_documents] count={len(recent_docs)} sample={recent_docs[:2]}")

#         # ===== sets robustos para grades =====
#         SKIP_VALUES, OK_VALUES = _grade_sets()
#         print(f"[grades] SKIP_VALUES={SKIP_VALUES}  OK_VALUES={OK_VALUES}")

#         # ===== reviews HOY (para completadas / precisión) usando TruncDate =====
#         reviews_today_all = (
#             ReviewLog.objects.filter(owner=user)
#             .annotate(d=TruncDate("created_at", tzinfo=tz) if USE_TZ else TruncDate("created_at"))
#             .filter(d=today_local)
#         )
#         total_reviews_today = reviews_today_all.count()
#         print(f"[reviews_today_all] count={total_reviews_today}")

#         # COMPLETADAS: tarjetas con algún intento NO-skip hoy y NINGÚN skip hoy
#         skip_fc_today = set(
#             reviews_today_all.filter(grade__in=SKIP_VALUES)
#             .values_list("flashcard", flat=True).distinct()
#         )
#         completed_today = (
#             reviews_today_all.exclude(grade__in=SKIP_VALUES)
#             .exclude(flashcard__in=skip_fc_today)
#             .values("flashcard").distinct().count()
#         )
#         print(f"[completed_today] completed={completed_today}  skip_fc_today={len(skip_fc_today)}")

#         # PRECISIÓN = correctas / intentos (sin skip)
#         reviews_today_for_acc = reviews_today_all.exclude(grade__in=SKIP_VALUES)
#         acc_den = reviews_today_for_acc.count()
#         acc_num = reviews_today_for_acc.filter(grade__in=OK_VALUES).count()

#         if acc_den == 0:
#             reviews_7d_for_acc = ReviewLog.objects.filter(
#                 owner=user, created_at__gte=start7_filter
#             ).exclude(grade__in=SKIP_VALUES)
#             acc_den = reviews_7d_for_acc.count()
#             acc_num = reviews_7d_for_acc.filter(grade__in=OK_VALUES).count()

#         accuracy_pct = (acc_num * 100.0 / acc_den) if acc_den else 0.0
#         print(f"[accuracy] acc_den={acc_den} acc_num={acc_num} accuracy_pct={accuracy_pct:.2f}")

#         # ===== temas (solo los con pendientes HOY) =====
#         themes_qs = (
#             Flashcard.objects.filter(owner=user)
#             .exclude(Q(theme__isnull=True) | Q(theme=""))          # quita esto si quieres "(Sin tema)"
#             .values("theme")
#             .annotate(
#                 total=Count("id"),
#                 pending_today=Count(
#                     "id",
#                     filter=Q(
#                         next_review__isnull=False
#                     ) & Q(
#                         # aunque arriba medimos due_today por TruncDate,
#                         # aquí dejamos la ventana del día por eficiencia de DB + tz
#                         next_review__gte=start_today_filter,
#                         next_review__lt=end_today_filter,
#                     ),
#                 ),
#                 pending_now=Count(
#                     "id",
#                     filter=Q(next_review__isnull=False, next_review__lte=now_for_overdue),
#                 ),
#             )
#             .order_by("-pending_today", "-pending_now", "-total")
#         )
#         themes_list = [t for t in themes_qs if t["pending_today"] > 0][:24]
#         print(f"[themes] count={len(themes_list)} sample={themes_list[:3]}")

#         # ===== pendientes por documento HOY (opcional para tu UI) =====
#         by_doc_qs = (
#             Document.objects.filter(owner=user)
#             .annotate(
#                 pending_today=Count(
#                     "flashcards",
#                     filter=Q(
#                         flashcards__next_review__isnull=False,
#                         flashcards__next_review__gte=start_today_filter,
#                         flashcards__next_review__lt=end_today_filter,
#                     ),
#                 )
#             )
#             .filter(pending_today__gt=0)
#             .values("id", "title", "pending_today")
#             .order_by("-pending_today", "title")
#         )
#         by_document_today = list(by_doc_qs)
#         print(f"[by_document_today] count={len(by_document_today)} sample={by_document_today[:3]}")

#         # ===== reviews últimos 7 días (gráfico) =====
#         reviews_7d = (
#             ReviewLog.objects.filter(owner=user, created_at__gte=start7_filter)
#             .annotate(d=trunc_expr)
#             .values("d")
#             .annotate(count=Count("id"))
#             .order_by("d")
#         )
#         bucket = {row["d"]: row["count"] for row in reviews_7d}

#         last7 = []
#         for i in range(7):
#             day = start7_local_date + timedelta(days=i)
#             last7.append({"date": day.isoformat(), "count": bucket.get(day, 0)})
#         print(f"[last7] {last7}")

#         # ===== racha (no cuenta "skip") =====
#         days_with_review = set(
#             ReviewLog.objects.filter(owner=user)
#             .exclude(grade__in=SKIP_VALUES)
#             .annotate(d=trunc_expr)
#             .values_list("d", flat=True)
#         )
#         streak = 0
#         cursor = today_local
#         while cursor in days_with_review:
#             streak += 1
#             cursor = cursor - timedelta(days=1)
#         print(f"[streak] {streak}")

#         # ===== bloque "hoy" para tu UI =====
#         today_block = {
#             "pending": due_today,                 # Pendientes HOY (coincide con 'Estudiar Hoy')
#             "completed": completed_today,         # Distintas fc completadas hoy (sin skip y sin mezclas con skip)
#             "new_cards": total_flashcards,        # Total flashcards del usuario (como pediste)
#             "accuracy_pct": round(accuracy_pct, 1),
#         }
#         print(f"[today_block] {today_block}")

#         payload = {
#             "tz": tz.key,
#             "now_local": now_local.isoformat(),
#             "totals": {
#                 "folders": total_folders,
#                 "documents": total_documents,
#                 "flashcards": total_flashcards,
#             },
#             "today": today_block,
#             "due": {"overdue": due_overdue, "today": due_today},
#             "by_difficulty": by_difficulty,
#             "themes": themes_list,
#             "by_document_today": by_document_today,
#             "recent_documents": recent_docs,
#             "reviews_last_7d": last7,
#             "streak": streak,
#             # paquete de depuración extra (opcional)
#             "debug": {
#                 "today": str(today_local),
#                 "reviews_today_all": total_reviews_today,
#                 "skip_fc_today": len(skip_fc_today),
#                 "non_skip_today": reviews_today_for_acc.count(),
#                 "acc_num": acc_num,
#             },
#         }

#         # imprime el payload (recortado para no explotar la consola)
#         try:
#             pretty = json.dumps(payload, ensure_ascii=False, default=str)
#             print(f"[payload.len]={len(pretty)}  [payload.sample]={pretty[:1200]}...")
#         except Exception as e:
#             print(f"[payload.print.error] {e}")

#         print("================= /DASHBOARD DEBUG ================\n")
#         return Response(payload)



def _grade_sets():
    """
    Sets robustos para filtrar por grade:
      OK    -> "facil", "parcialmente", "esfuerzo" (+ good/easy)
      SKIP  -> "saltar" (+ skip)
    Además soporta constantes del modelo (GOOD/EASY/SKIP) si existen.
    """
    values = []
    for attr in ("SKIP", "GOOD", "EASY"):
        if hasattr(ReviewLog, attr):
            values.append(getattr(ReviewLog, attr))

    lower_map = {str(v).lower(): v for v in values}

    SKIP_VALUES = set()
    OK_VALUES   = set()

    # Constantes del modelo (si existen)
    if "skip" in lower_map:
        SKIP_VALUES.add(lower_map["skip"])
    if "good" in lower_map:
        OK_VALUES.add(lower_map["good"])
    if "easy" in lower_map:
        OK_VALUES.add(lower_map["easy"])

    # Alias ES/EN
    SKIP_VALUES.update(["saltar", "skip"])
    OK_VALUES.update(["facil", "parcialmente", "esfuerzo", "easy", "good"])

    return SKIP_VALUES, OK_VALUES


class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # ===== TZ =====
        USE_TZ = bool(getattr(settings, "USE_TZ", True))
        default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
        tzname = request.query_params.get("tz") or default_tzname
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo(default_tzname)

        # ===== tiempos base según USE_TZ =====
        if USE_TZ:
            now_utc = dj_tz.now()                 # aware UTC
            now_local = now_utc.astimezone(tz)    # aware local
            today_local = now_local.date()

            start_today_local  = datetime.combine(today_local, time.min, tzinfo=tz)
            end_today_local    = start_today_local + timedelta(days=1)
            start_today_filter = start_today_local.astimezone(dt_timezone.utc)
            end_today_filter   = end_today_local.astimezone(dt_timezone.utc)

            now_for_overdue   = now_utc

            # últimos 7 días (incluye hoy) en local -> a UTC para filtrar
            start7_local_date = today_local - timedelta(days=6)
            start7_local      = datetime.combine(start7_local_date, time.min, tzinfo=tz)
            start7_filter     = start7_local.astimezone(dt_timezone.utc)

            trunc_expr = TruncDate("created_at", tzinfo=tz)
        else:
            now_local = datetime.now()
            today_local = now_local.date()

            start_today_filter = datetime.combine(today_local, time.min)
            end_today_filter   = start_today_filter + timedelta(days=1)
            now_for_overdue    = now_local

            start7_local_date  = today_local - timedelta(days=6)
            start7_filter      = datetime.combine(start7_local_date, time.min)

            trunc_expr = TruncDate("created_at")

        print("\n================= DASHBOARD DEBUG =================")
        print(f"[user] id={getattr(user, 'id', None)}  username={getattr(user, 'username', None)}")
        print(f"[tz] tzname={tz.key}  USE_TZ={USE_TZ}")
        if USE_TZ:
            print(f"[time] now_utc={now_utc}  now_local={now_local.isoformat()}")
            print(f"[time] today_local={today_local}  start_today_utc={start_today_filter}  end_today_utc={end_today_filter}")
            print(f"[time] start7_filter(UTC)={start7_filter}")
        else:
            print(f"[time] now_local={now_local.isoformat()}  today_local={today_local}")
            print(f"[time] start_today={start_today_filter}  end_today={end_today_filter}")
            print(f"[time] start7_filter(local)={start7_filter}")

        # ===== totales =====
        total_folders    = Folder.objects.filter(owner=user).count()
        total_documents  = Document.objects.filter(owner=user).count()
        total_flashcards = Flashcard.objects.filter(owner=user).count()
        print(f"[totals] folders={total_folders} documents={total_documents} flashcards={total_flashcards}")

        # ===== pendientes =====
        # AHORA (vencidas a este instante)
        due_overdue = Flashcard.objects.filter(
            owner=user, next_review__isnull=False, next_review__lte=now_for_overdue
        ).count()

        # HOY (TruncDate evita problemas UTC/local)
        due_today = (
            Flashcard.objects
            .filter(owner=user)
            .annotate(d=TruncDate("next_review", tzinfo=tz) if USE_TZ else TruncDate("next_review"))
            .filter(d=today_local)
            .count()
        )
        print(f"[due] overdue(now)={due_overdue}  today={due_today}")

        # ===== por dificultad =====
        diff_counts = (
            Flashcard.objects.filter(owner=user)
            .values("difficulty")
            .annotate(count=Count("id"))
        )
        by_difficulty = {row["difficulty"] or "": row["count"] for row in diff_counts}
        for k in ["olvide", "parcialmente", "esfuerzo", "facil", "saltar"]:
            by_difficulty.setdefault(k, 0)
        print(f"[by_difficulty] {by_difficulty}")

        # ===== documentos recientes + métricas =====
        recent_qs = (
            Document.objects.filter(owner=user)
            .annotate(
                flashcards_count=Count("flashcards", distinct=True),
                next_due=Min("flashcards__next_review"),
            )
            .order_by("-updated_at")[:12]
            .values(
                "id", "title", "created_at", "updated_at",
                "flashcards_count", "next_due", "folder_id"
            )
        )
        recent_docs = []
        for d in recent_qs:
            created_at = d["created_at"]
            updated_at = d["updated_at"]
            next_due   = d["next_due"]
            out = dict(d)

            if USE_TZ:
                out["created_at_local"] = created_at.astimezone(tz).isoformat() if created_at else None
                out["updated_at_local"] = updated_at.astimezone(tz).isoformat() if updated_at else None
                out["next_due_local"]   = next_due.astimezone(tz).isoformat()   if next_due else None
            else:
                out["created_at_local"] = created_at.isoformat() if created_at else None
                out["updated_at_local"] = updated_at.isoformat() if updated_at else None
                out["next_due_local"]   = next_due.isoformat()   if next_due else None

            recent_docs.append(out)
        print(f"[recent_documents] count={len(recent_docs)} sample={recent_docs[:2]}")

        # ===== sets robustos para grades =====
        # SKIP_VALUES, OK_VALUES = _grade_sets()
        # print(f"[grades] SKIP_VALUES={SKIP_VALUES}  OK_VALUES={OK_VALUES}")

        # # ===== reviews HOY (para completadas / precisión) =====
        # reviews_today_all = (
        #     ReviewLog.objects.filter(owner=user)
        #     .annotate(d=TruncDate("created_at", tzinfo=tz) if USE_TZ else TruncDate("created_at"))
        #     .filter(d=today_local)
        # )
        # total_reviews_today = reviews_today_all.count()
        # print(f"[reviews_today_all] count={total_reviews_today}")
        SKIP_VALUES, OK_VALUES = _grade_sets()
        print(f"[grades] SKIP_VALUES={SKIP_VALUES}  OK_VALUES={OK_VALUES}")

        # ===== reviews HOY (para completadas / precisión) =====
        reviews_today_all = (
            ReviewLog.objects.filter(owner=user)
            .annotate(d=TruncDate("created_at", tzinfo=tz) if USE_TZ else TruncDate("created_at"))
            .filter(d=today_local)
        )
        total_reviews_today = reviews_today_all.count()
        print(f"[reviews_today_all] count={total_reviews_today}")

        # ------------ COMPLETADAS ------------
        # # 1) flashcards con ≥1 review OK (facil/parcialmente/esfuerzo) hoy
        # ok_fc_today_ids = set(
        #     reviews_today_all.filter(grade__in=OK_VALUES)
        #     .values_list("flashcard", flat=True).distinct()
        # )

        # # 2) de esas, que su next_review NO caiga hoy (o sea nula)
        # fc_ok_qs = Flashcard.objects.filter(id__in=ok_fc_today_ids)
        # if USE_TZ:
        #     fc_ok_qs = fc_ok_qs.annotate(d=TruncDate("next_review", tzinfo=tz))
        # else:
        #     fc_ok_qs = fc_ok_qs.annotate(d=TruncDate("next_review"))

        # completed_today = fc_ok_qs.filter(
        #     Q(next_review__isnull=True) | ~Q(d=today_local)
        # ).count()

        # print(f"[completed_today] completed={completed_today}  ok_fc_today={len(ok_fc_today_ids)}")
        completed_today = 0
        if total_reviews_today > 0:
            ok_fc_today_ids = set(
                reviews_today_all.filter(grade__in=OK_VALUES)
                .values_list("flashcard", flat=True).distinct()
            )

            d_next_expr = TruncDate("next_review", tzinfo=tz) if USE_TZ else TruncDate("next_review")
            fc_ok_qs = Flashcard.objects.filter(id__in=ok_fc_today_ids).annotate(d_next=d_next_expr)

            completed_today = fc_ok_qs.filter(
                Q(next_review__isnull=True) | ~Q(d_next=today_local)
            ).count()
        else:
            # Fallback SIN ReviewLog:
            # tarjetas tocadas hoy (updated_at hoy) con difficulty OK
            # y next_review NO cae hoy (o es NULL)
            d_upd_expr  = TruncDate("updated_at", tzinfo=tz) if USE_TZ else TruncDate("updated_at")
            d_next_expr = TruncDate("next_review", tzinfo=tz) if USE_TZ else TruncDate("next_review")

            completed_today = (
                Flashcard.objects.filter(owner=user)
                .annotate(d_upd=d_upd_expr, d_next=d_next_expr)
                .filter(d_upd=today_local)
                .filter(difficulty__in=OK_VALUES)
                .filter(Q(next_review__isnull=True) | ~Q(d_next=today_local))
                .count()
            )

        print(f"[completed_today] completed={completed_today}")


        # ------------ PRECISIÓN ------------
        # precisión = OK / (intentos SIN skip) — hoy; si 0, fallback a últimos 7 días
        # reviews_today_nonskip = reviews_today_all.exclude(grade__in=SKIP_VALUES)
        # acc_den = reviews_today_nonskip.count()
        # acc_num = reviews_today_nonskip.filter(grade__in=OK_VALUES).count()

        # if acc_den == 0:
        #     reviews_7d_nonskip = ReviewLog.objects.filter(
        #         owner=user, created_at__gte=start7_filter
        #     ).exclude(grade__in=SKIP_VALUES)
        #     acc_den = reviews_7d_nonskip.count()
        #     acc_num = reviews_7d_nonskip.filter(grade__in=OK_VALUES).count()

        # accuracy_pct = (acc_num * 100.0 / acc_den) if acc_den else 0.0
        # print(f"[accuracy] acc_den={acc_den} acc_num={acc_num} accuracy_pct={accuracy_pct:.2f}")

        # Ideal (con ReviewLog): OK / (no-skip) de HOY; si no hay, 7d; si tampoco, fallback a updated_at de HOY
        reviews_today_nonskip = reviews_today_all.exclude(grade__in=SKIP_VALUES)
        acc_den = reviews_today_nonskip.count()
        acc_num = reviews_today_nonskip.filter(grade__in=OK_VALUES).count()

        if acc_den == 0:
            reviews_7d_nonskip = (
                ReviewLog.objects.filter(owner=user, created_at__gte=start7_filter)
                .exclude(grade__in=SKIP_VALUES)
            )
            acc_den = reviews_7d_nonskip.count()
            acc_num = reviews_7d_nonskip.filter(grade__in=OK_VALUES).count()

        if acc_den == 0:
            # Fallback SIN ReviewLog: usa Flashcard.updated_at de HOY
            d_upd_expr = TruncDate("updated_at", tzinfo=tz) if USE_TZ else TruncDate("updated_at")
            attempts_qs = (
                Flashcard.objects.filter(owner=user)
                .annotate(d_upd=d_upd_expr)
                .filter(d_upd=today_local)
            )
            acc_den = attempts_qs.exclude(difficulty__in=SKIP_VALUES).count()
            acc_num = attempts_qs.filter(difficulty__in=OK_VALUES).count()

        accuracy_pct = (acc_num * 100.0 / acc_den) if acc_den else 0.0
        print(f"[accuracy] acc_den={acc_den} acc_num={acc_num} accuracy_pct={accuracy_pct:.2f}")
        # ===== temas (solo los con pendientes HOY) =====
        themes_qs = (
            Flashcard.objects.filter(owner=user)
            .exclude(Q(theme__isnull=True) | Q(theme=""))  # quita esto si quieres "(Sin tema)"
            .values("theme")
            .annotate(
                total=Count("id"),
                pending_today=Count(
                    "id",
                    filter=Q(next_review__isnull=False) & Q(
                        next_review__gte=start_today_filter,
                        next_review__lt=end_today_filter,
                    ),
                ),
                pending_now=Count(
                    "id",
                    filter=Q(next_review__isnull=False, next_review__lte=now_for_overdue),
                ),
            )
            .order_by("-pending_today", "-pending_now", "-total")
        )
        themes_list = [t for t in themes_qs if t["pending_today"] > 0][:24]
        print(f"[themes] count={len(themes_list)} sample={themes_list[:3]}")

        # ===== pendientes por documento HOY (opcional para tu UI) =====
        by_doc_qs = (
            Document.objects.filter(owner=user)
            .annotate(
                pending_today=Count(
                    "flashcards",
                    filter=Q(
                        flashcards__next_review__isnull=False,
                        flashcards__next_review__gte=start_today_filter,
                        flashcards__next_review__lt=end_today_filter,
                    ),
                )
            )
            .filter(pending_today__gt=0)
            .values("id", "title", "pending_today")
            .order_by("-pending_today", "title")
        )
        by_document_today = list(by_doc_qs)
        print(f"[by_document_today] count={len(by_document_today)} sample={by_document_today[:3]}")

        # ===== reviews últimos 7 días (gráfico) =====
        reviews_7d = (
            ReviewLog.objects.filter(owner=user, created_at__gte=start7_filter)
            .annotate(d=trunc_expr)
            .values("d")
            .annotate(count=Count("id"))
            .order_by("d")
        )
        bucket = {row["d"]: row["count"] for row in reviews_7d}

        last7 = []
        for i in range(7):
            day = start7_local_date + timedelta(days=i)
            last7.append({"date": day.isoformat(), "count": bucket.get(day, 0)})
        print(f"[last7] {last7}")

        # ===== racha (días con alguna respuesta OK) =====
        # days_with_review = set(
        #     ReviewLog.objects.filter(owner=user, grade__in=OK_VALUES)
        #     .annotate(d=trunc_expr)
        #     .values_list("d", flat=True)
        # )
        # streak = 0
        # cursor = today_local
        # while cursor in days_with_review:
        #     streak += 1
        #     cursor = cursor - timedelta(days=1)
        # print(f"[streak] {streak}")
        trunc_expr = TruncDate("created_at", tzinfo=tz) if USE_TZ else TruncDate("created_at")
        days_with_review = set(
            ReviewLog.objects.filter(owner=user, grade__in=OK_VALUES)
            .annotate(d=trunc_expr)
            .values_list("d", flat=True)
        )

        # Fallback: si no hay ReviewLog, usa días con Flashcard.updated_at y difficulty OK
        if not days_with_review:
            trunc_upd = TruncDate("updated_at", tzinfo=tz) if USE_TZ else TruncDate("updated_at")
            days_with_review = set(
                Flashcard.objects.filter(owner=user, difficulty__in=OK_VALUES)
                .annotate(d=trunc_upd)
                .values_list("d", flat=True)
            )

        streak = 0
        cursor = today_local
        while cursor in days_with_review:
            streak += 1
            cursor = cursor - timedelta(days=1)
        print(f"[streak] {streak}")

        # ===== bloque "hoy" para tu UI =====
        today_block = {
            "pending": due_today,          # Pendientes HOY
            "completed": completed_today,  # OK hoy y next_review fuera de hoy (o NULL)
            "new_cards": total_flashcards, # Total flashcards del usuario (como pediste)
            "accuracy_pct": round(accuracy_pct, 1),
        }
        print(f"[today_block] {today_block}")

        payload = {
            "tz": tz.key,
            "now_local": now_local.isoformat(),
            "totals": {
                "folders": total_folders,
                "documents": total_documents,
                "flashcards": total_flashcards,
            },
            "today": today_block,
            "due": {"overdue": due_overdue, "today": due_today},
            "by_difficulty": by_difficulty,
            "themes": themes_list,
            "by_document_today": by_document_today,
            "recent_documents": recent_docs,
            "reviews_last_7d": last7,
            "streak": streak,
            "debug": {
                "today": str(today_local),
                "reviews_today_all": total_reviews_today,
                "acc_num": acc_num,
                "acc_den": acc_den,
            },
        }

        try:
            pretty = json.dumps(payload, ensure_ascii=False, default=str)
            print(f"[payload.len]={len(pretty)}  [payload.sample]={pretty[:1200]}...")
        except Exception as e:
            print(f"[payload.print.error] {e}")

        print("================= /DASHBOARD DEBUG ================\n")
        return Response(payload)


class FlashcardListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FlashcardSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Flashcard.objects.filter(owner=user)

        # filtros
        theme = self.request.query_params.get("theme")
        folder = self.request.query_params.get("folder")
        due   = self.request.query_params.get("due")

        USE_TZ = bool(getattr(settings, "USE_TZ", True))
        default_tzname = getattr(settings, "TIME_ZONE", None) or "America/Lima"
        tzname = self.request.query_params.get("tz") or default_tzname
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo(default_tzname)

        if USE_TZ:
            now_utc = dj_tz.now()
            now_local = now_utc.astimezone(tz)
            today_local = now_local.date()
        else:
            now_local = datetime.now()
            today_local = now_local.date()

        print("\n----------- FlashcardListView DEBUG -----------")
        print(f"[user] id={getattr(user, 'id', None)} tz={tz.key} USE_TZ={USE_TZ}")
        print(f"[params] theme={theme} folder={folder} due={due} today_local={today_local}")

        if theme:
            qs = qs.filter(theme=theme)
        if folder:
            qs = qs.filter(document__folder_id=folder)

        if USE_TZ:
            if due == "now":
                qs = qs.filter(next_review__isnull=False, next_review__lte=now_utc)
                print(f"[filter] due=now -> next_review <= {now_utc}")
            elif due == "today":
                qs = qs.annotate(d=TruncDate("next_review", tzinfo=tz)).filter(d=today_local)
                print(f"[filter] due=today -> TruncDate(next_review)=={today_local} (tz={tz.key})")
        else:
            if due == "now":
                qs = qs.filter(next_review__isnull=False, next_review__lte=now_local)
                print(f"[filter] due=now -> next_review <= {now_local}")
            elif due == "today":
                qs = qs.annotate(d=TruncDate("next_review")).filter(d=today_local)
                print(f"[filter] due=today -> TruncDate(next_review)=={today_local} (naive)")

        qs = qs.order_by("next_review", "id")
        count = qs.count()
        sample = list(qs.values("id", "theme", "difficulty", "next_review")[:5])
        print(f"[result] count={count} sample={sample}")
        print("----------- /FlashcardListView DEBUG ----------\n")

        return qs