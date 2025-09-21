from rest_framework import viewsets, permissions
from django.db.models import Q
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
    @action(detail=True, methods=["POST"], url_path="review")
    def review(self, request, pk=None):
        """Scheduler básico: ajusta next_review y guarda ReviewLog."""
        card: Flashcard = self.get_object()
        grade = request.data.get("grade")
        duration_ms = int(request.data.get("duration_ms") or 0)

        add_days = {"again": 0, "hard": 1, "good": 3, "easy": 5}.get(grade, 1)
        next_rev = timezone.now() + timezone.timedelta(days=add_days)
        card.next_review = next_rev
        card.review_count = (card.review_count or 0) + 1
        card.owner = request.user  # por si acaso
        card.save(update_fields=["next_review", "review_count", "owner", "updated_at"])

        ReviewLog.objects.create(
            owner=request.user,
            flashcard=card,
            grade=grade,
            interval_days=add_days,
            next_review=next_rev,
            duration_ms=duration_ms,
        )
        return Response(self.get_serializer(card).data, status=status.HTTP_200_OK)

class ReviewLogViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ReviewLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ReviewLog.objects.select_related("flashcard")

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)