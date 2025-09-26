# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views import FolderViewSet, DocumentViewSet, BlockViewSet, FlashcardViewSet, ReviewLogViewSet

# router = DefaultRouter()
# router.register(r"folders", FolderViewSet, basename="folder")
# router.register(r"documents", DocumentViewSet, basename="document")
# router.register(r"blocks", BlockViewSet, basename="block")
# router.register(r"flashcards", FlashcardViewSet, basename="flashcard")
# router.register(r"reviews", ReviewLogViewSet, basename="reviewlog")

# urlpatterns = router.urls

# knowledge/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FolderViewSet, DocumentViewSet, BlockViewSet, FlashcardViewSet, ReviewLogViewSet,
    DashboardSummaryView,FlashcardListView   # <-- importa la vista del dashboard
)

router = DefaultRouter()
router.register(r"folders", FolderViewSet, basename="folder")
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"flashcards", FlashcardViewSet, basename="flashcard")
router.register(r"reviews", ReviewLogViewSet, basename="reviewlog")

# urlpatterns = [
#     # endpoint del dashboard (usa ?tz=America/Lima si quieres forzar zona horaria)
#     path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    

#     # el resto de rutas del router
#     path("", include(router.urls)),
# ]
urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("flashcardsList/", FlashcardListView.as_view(), name="flashcard-list"),
] + router.urls