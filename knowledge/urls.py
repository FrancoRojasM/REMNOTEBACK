from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FolderViewSet, DocumentViewSet, BlockViewSet, FlashcardViewSet, ReviewLogViewSet

router = DefaultRouter()
router.register(r"folders", FolderViewSet, basename="folder")
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"blocks", BlockViewSet, basename="block")
router.register(r"flashcards", FlashcardViewSet, basename="flashcard")
router.register(r"reviews", ReviewLogViewSet, basename="reviewlog")

urlpatterns = router.urls
