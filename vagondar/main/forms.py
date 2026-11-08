from django import forms

from .models import Destination, TariffHistory, TrainEvent, Wagon


class AddWagonForm(forms.ModelForm):
    class Meta:
        model = Wagon
        fields = ["wagon_number", "destination", "notes"]
        labels = {"wagon_number": "Номер вагона", "destination": "Направление", "notes": "Заметка"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class AddEventForm(forms.ModelForm):
    class Meta:
        model = TrainEvent
        fields = ["operation_type", "event_date", "event_time", "tariff", "notes"]
        labels = {
            "operation_type": "Тип события",
            "event_date": "Дата",
            "event_time": "Время",
            "tariff": "Тариф",
            "notes": "Заметка",
        }
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "event_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tariff"].queryset = TariffHistory.objects.order_by("-start_date")
        self.fields["tariff"].empty_label = "Авто (по дате события)"


class AddDestinationForm(forms.ModelForm):
    class Meta:
        model = Destination
        fields = ["name", "distance_km"]
        labels = {"name": "Название предприятия", "distance_km": "Расстояние, км"}


class AddTariffForm(forms.ModelForm):
    class Meta:
        model = TariffHistory
        fields = ["start_date", "tariff"]
        labels = {"start_date": "Действует с", "tariff": "Тариф, ₸"}
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
