from rest_framework import viewsets, permissions
from django.db.models import Q
from datetime import timedelta

from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Block, Flashcard, ReviewLog
from .serializers import BlockSerializer, FlashcardSerializer, ReviewLogSerializer,FolderSerializer,Folder,DocumentSerializer
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Block, Flashcard, ReviewLog,Document
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
        return qs

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