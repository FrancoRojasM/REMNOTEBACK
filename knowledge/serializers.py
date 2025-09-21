from rest_framework import serializers
from .models import Folder, Document
from .models import Block, Flashcard, ReviewLog


class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ["id", "name", "parent", "position"]

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "folder", "content", "created_at", "updated_at"]

class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Block
        fields = ["id", "document", "parent", "order", "type", "content", "level", "heading_level", "created_at", "updated_at"]

class FlashcardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flashcard
        fields = ["id", "document", "block", "type", "front", "back", "theme", "difficulty", "next_review", "review_count", "created_at", "updated_at"]

class ReviewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewLog
        fields = ["id", "flashcard", "grade", "interval_days", "ease", "next_review", "duration_ms", "created_at"]