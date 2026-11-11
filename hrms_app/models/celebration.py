from django.db import models
from django.utils.translation import gettext_lazy as _

from .core import CustomUser


class CelebrationWish(models.Model):
    """One employee's wish to a colleague on a birthday or anniversary."""

    BIRTHDAY, MARRIAGE, WORK = "birthday", "marriage", "work"
    KIND_CHOICES = [
        (BIRTHDAY, _("Birthday")),
        (MARRIAGE, _("Wedding Anniversary")),
        (WORK, _("Work Anniversary")),
    ]

    sender = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="wishes_sent", verbose_name=_("From")
    )
    receiver = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="wishes_received", verbose_name=_("To")
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name=_("Occasion"))
    occasion_date = models.DateField(verbose_name=_("Occasion Date"))
    message = models.CharField(max_length=300, verbose_name=_("Message"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        db_table = "tbl_celebration_wish"
        verbose_name = _("Celebration Wish")
        verbose_name_plural = _("Celebration Wishes")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "receiver", "kind", "occasion_date"], name="unique_celebration_wish"
            )
        ]
        indexes = [models.Index(fields=["receiver", "occasion_date"], name="idx_wish_receiver_date")]

    def __str__(self):
        return f"{self.sender} -> {self.receiver} ({self.kind}, {self.occasion_date})"
