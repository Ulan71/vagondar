from django.core.validators import MinValueValidator
from django.db import models


class Destination(models.Model):
    name = models.CharField(max_length=100)
    distance_km = models.DecimalField(
        max_digits=6, decimal_places=4, validators=[MinValueValidator(0)]
    )

    def __str__(self):
        return f"{self.name} | {round(self.distance_km, 3)} км"


class TariffHistory(models.Model):
    start_date = models.DateField()
    tariff = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        amount = f"{self.tariff:,.2f}".replace(",", " ").replace(".", ",")
        return f"{amount} ₸ с {self.start_date:%d.%m.%Y}"

    @classmethod
    def for_date(cls, date):
        """Тариф, действующий на указанную дату (последний с start_date <= date)."""
        return cls.objects.filter(start_date__lte=date).order_by("-start_date").first()


class TrainEvent(models.Model):
    OPERATION_CHOICES = [
        ('arrival', 'Пригон'),
        ('removal', 'Уборка'),
    ]

    operation_type = models.CharField(max_length=10, choices=OPERATION_CHOICES)
    event_date = models.DateField()
    event_time = models.TimeField()
    tariff = models.ForeignKey(
        TariffHistory, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Если не выбран — подставится тариф, действующий на дату события.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.tariff_id is None and self.event_date:
            self.tariff = TariffHistory.for_date(self.event_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_operation_type_display()} {self.event_date} | {self.event_time}"


class Wagon(models.Model):
    wagon_number = models.CharField(max_length=20)
    event = models.ForeignKey(TrainEvent, on_delete=models.CASCADE, related_name='wagons')
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        # PostgreSQL без ORDER BY не гарантирует порядок — фиксируем порядок добавления
        ordering = ["id"]

    def __str__(self):
        return f"{self.wagon_number} (событие: {self.event_id}) | {self.destination}"
