import re

from django import forms

from .models import Destination, TariffHistory, TrainEvent, Wagon


class BootstrapMixin:
    """Добавляет bootstrap-классы всем виджетам формы."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css = "form-select" if isinstance(widget, forms.Select) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


def destination_queryset():
    return Destination.objects.order_by("name")


class AddWagonForm(BootstrapMixin, forms.ModelForm):
    """Редактирование одного вагона."""

    class Meta:
        model = Wagon
        fields = ["wagon_number", "destination", "notes"]
        labels = {"wagon_number": "Номер вагона", "destination": "Направление", "notes": "Заметка"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].queryset = destination_queryset()
        self.fields["destination"].required = True


class AddWagonsForm(BootstrapMixin, forms.Form):
    """Добавление сразу нескольких вагонов с одним направлением."""

    wagon_numbers = forms.CharField(
        label="Номера вагонов",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "По одному в строке или через пробел/запятую"}),
    )
    destination = forms.ModelChoiceField(label="Направление", queryset=Destination.objects.none())
    notes = forms.CharField(label="Заметка", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination"].queryset = destination_queryset()

    def clean_wagon_numbers(self):
        numbers = [n for n in re.split(r"[\s,;]+", self.cleaned_data["wagon_numbers"]) if n]
        if not numbers:
            raise forms.ValidationError("Введите хотя бы один номер.")
        max_len = Wagon._meta.get_field("wagon_number").max_length
        too_long = [n for n in numbers if len(n) > max_len]
        if too_long:
            raise forms.ValidationError(f"Слишком длинный номер (макс. {max_len} символов): {', '.join(too_long)}")
        return numbers

    def save(self, event):
        wagons = [
            Wagon(event=event, wagon_number=number, destination=self.cleaned_data["destination"],
                  notes=self.cleaned_data["notes"] or None)
            for number in self.cleaned_data["wagon_numbers"]
        ]
        return Wagon.objects.bulk_create(wagons)


class AddEventForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TrainEvent
        fields = ["operation_type", "event_date", "event_time", "tariff", "notes"]
        labels = {
            "operation_type": "Тип операции",
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
        self.fields["tariff"].help_text = ""


class AddDestinationForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Destination
        fields = ["name", "distance_km"]
        labels = {"name": "Название предприятия", "distance_km": "Расстояние, км"}
        widgets = {"distance_km": forms.NumberInput(attrs={"step": "0.0001", "min": "0"})}


class AddTariffForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TariffHistory
        fields = ["start_date", "tariff"]
        labels = {"start_date": "Действует с", "tariff": "Тариф, ₸"}
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
