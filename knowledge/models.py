from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Folder(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=200)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name

class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    content = models.JSONField(default=list, blank=True)  # bloques del editor
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return self.title


class Block(TimeStamped):
    TEXT = "text"
    FLASHCARD = "flashcard"
    LIST = "list"
    HEADING = "heading"
    TYPE_CHOICES = [
        (TEXT, "text"),
        (FLASHCARD, "flashcard"),
        (LIST, "list"),
        (HEADING, "heading"),
    ]

    document = models.ForeignKey("Document", on_delete=models.CASCADE, related_name="blocks")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    order = models.PositiveIntegerField(default=0)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TEXT)
    content = models.TextField(blank=True, default="")
    level = models.PositiveIntegerField(null=True, blank=True)         # para listas
    heading_level = models.PositiveIntegerField(null=True, blank=True) # 1..6 para headings

    class Meta:
        ordering = ["order", "created_at"]

class Flashcard(TimeStamped):
    BASIC = "basic"
    ANTERIOR = "anterior"
    POSTERIOR = "posterior"
    DOBLE = "doble"
    CLOZE = "cloze"
    MULTIPLE = "multiple"
    TYPE_CHOICES = [
        (BASIC, "basic"),
        (ANTERIOR, "anterior"),
        (POSTERIOR, "posterior"),
        (DOBLE, "doble"),
        (CLOZE, "cloze"),
        (MULTIPLE, "multiple"),
    ]

    DIFFICULTY_CHOICES = [
        ("muy-facil", "muy-facil"),
        ("facil", "facil"),
        ("medio", "medio"),
        ("dificil", "dificil"),
        ("muy-dificil", "muy-dificil"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flashcards")
    document = models.ForeignKey("Document", on_delete=models.CASCADE, related_name="flashcards")
    block = models.ForeignKey("Block", null=True, blank=True, on_delete=models.SET_NULL, related_name="flashcards")

    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=BASIC)
    front = models.TextField()
    back = models.TextField()
    theme = models.CharField(max_length=200, blank=True, default="")
    difficulty = models.CharField(max_length=12, choices=DIFFICULTY_CHOICES, default="facil")

    next_review = models.DateTimeField(null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["owner", "next_review"])]

class ReviewLog(TimeStamped):
    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"
    GRADE_CHOICES = [(AGAIN, AGAIN), (HARD, HARD), (GOOD, GOOD), (EASY, EASY)]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="review_logs")
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name="reviews")
    grade = models.CharField(max_length=8, choices=GRADE_CHOICES)
    interval_days = models.PositiveIntegerField(default=0)
    ease = models.FloatField(default=2.5)
    next_review = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]