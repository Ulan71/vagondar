from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, TemplateView

from . import forms
from .calculations import calculate_event
from .excel import XLSX_CONTENT_TYPE, build_workbook
from .models import Destination, TariffHistory, TrainEvent, Wagon


def events_queryset():
    wagons = Wagon.objects.select_related("destination").order_by("id")
    return (
        TrainEvent.objects
        .select_related("tariff")
        .prefetch_related(Prefetch("wagons", queryset=wagons))
        .order_by("-event_date", "-event_time")
    )


def redirect_back(request, fallback="main"):
    """Возвращает пользователя туда, откуда пришёл запрос (сохраняет страницу и поиск)."""
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(referer)
    return redirect(fallback)


def form_errors_text(form):
    parts = []
    for field_name, errors in form.errors.items():
        label = form.fields[field_name].label if field_name in form.fields else ""
        parts.append(f"{label}: {' '.join(errors)}" if label else " ".join(errors))
    return "; ".join(parts)


def parse_date(text):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


class MainViews(LoginRequiredMixin, ListView):
    template_name = "main/index.html"
    context_object_name = "events"
    paginate_by = 25

    # action_type -> (класс формы, сообщение об успехе)
    CREATE_ACTIONS = {
        "add_event": (forms.AddEventForm, "Событие добавлено"),
    }

    def get_queryset(self):
        qs = events_queryset()
        params = self.request.GET

        operation = params.get("op", "")
        if operation in dict(TrainEvent.OPERATION_CHOICES):
            qs = qs.filter(operation_type=operation)

        date_from = parse_date(params.get("date_from", ""))
        date_to = parse_date(params.get("date_to", ""))
        if date_from:
            qs = qs.filter(event_date__gte=date_from)
        if date_to:
            qs = qs.filter(event_date__lte=date_to)

        query = (params.get("search_events") or "").strip()
        if query:
            found_date = parse_date(query)
            if found_date:
                qs = qs.filter(event_date=found_date)
            else:
                condition = Q(wagons__wagon_number__icontains=query)
                if query.isdigit():
                    condition |= Q(id=int(query))
                qs = qs.filter(condition).distinct()
        return qs

    def paginate_queryset(self, queryset, page_size):
        # get_page() вместо page(): несуществующая страница -> последняя, а не 404
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # auto_id разный, чтобы id полей в формах добавления и редактирования не совпадали
        context["add_wagons_form"] = forms.AddWagonsForm(auto_id="add_wagon_%s")
        context["edit_wagon_form"] = forms.AddWagonForm(auto_id="edit_wagon_%s")
        context["add_event_form"] = forms.AddEventForm(auto_id="add_event_%s")
        context["edit_event_form"] = forms.AddEventForm(auto_id="edit_event_%s")
        context.update(reference_forms())
        context["filters_active"] = any(
            self.request.GET.get(k) for k in ("search_events", "op", "date_from", "date_to"))
        for event in context["events"]:
            event.calc = calculate_event(event, list(event.wagons.all()))
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action_type")

        if action == "edit_event":
            event = get_object_or_404(TrainEvent, pk=request.POST.get("event_id") or 0)
            return self._save(forms.AddEventForm(request.POST, instance=event), "Событие изменено")

        if action == "edit_wagon":
            wagon = get_object_or_404(Wagon, pk=request.POST.get("wagon_id") or 0)
            return self._save(forms.AddWagonForm(request.POST, instance=wagon), "Вагон изменён")

        if action == "add_wagon":
            event = get_object_or_404(TrainEvent, pk=request.POST.get("event_id") or 0)
            form = forms.AddWagonsForm(request.POST)
            if form.is_valid():
                count = len(form.save(event))
                messages.success(request, f"Добавлено вагонов: {count}")
            else:
                messages.error(request, f"Не сохранено. {form_errors_text(form)}")
            return redirect_back(request)

        if action in self.CREATE_ACTIONS:
            form_class, success = self.CREATE_ACTIONS[action]
            return self._save(form_class(request.POST), success)

        messages.error(request, "Неизвестное действие.")
        return redirect_back(request)

    def _save(self, form, success_message):
        return save_form(self.request, form, success_message)


def save_form(request, form, success_message):
    if form.is_valid():
        form.save()
        messages.success(request, success_message)
    else:
        messages.error(request, f"Не сохранено. {form_errors_text(form)}")
    return redirect_back(request)


def reference_forms():
    return {
        "add_destination_form": forms.AddDestinationForm(auto_id="add_destination_%s"),
        "edit_destination_form": forms.AddDestinationForm(auto_id="edit_destination_%s"),
        "add_tariff_form": forms.AddTariffForm(auto_id="add_tariff_%s"),
        "edit_tariff_form": forms.AddTariffForm(auto_id="edit_tariff_%s"),
    }


def xlsx_response(content, filename):
    response = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ExportEventView(LoginRequiredMixin, View):
    def get(self, request, pk):
        event = get_object_or_404(events_queryset(), pk=pk)
        filename = f"vagondar_{event.event_date:%Y-%m-%d}_{event.operation_type}_{event.pk}.xlsx"
        return xlsx_response(build_workbook([event]), filename)


class ExportPeriodView(LoginRequiredMixin, View):
    def get(self, request):
        start = parse_date(request.GET.get("start_date", ""))
        end = parse_date(request.GET.get("end_date", ""))
        operation_type = request.GET.get("operation_type", "")

        if not start or not end:
            messages.error(request, "Укажите начальную и конечную дату для экспорта.")
            return redirect_back(request)
        if start > end:
            start, end = end, start

        events = events_queryset().filter(event_date__range=(start, end))
        if operation_type in dict(TrainEvent.OPERATION_CHOICES):
            events = events.filter(operation_type=operation_type)
        events = list(events.order_by("event_date", "event_time"))

        if not events:
            messages.warning(request, f"За период {start:%d.%m.%Y} – {end:%d.%m.%Y} событий нет.")
            return redirect_back(request)

        filename = f"vagondar_{start:%Y-%m-%d}_{end:%Y-%m-%d}.xlsx"
        return xlsx_response(build_workbook(events), filename)


class ReferencesView(LoginRequiredMixin, TemplateView):
    """Справочники: направления и тарифы."""
    template_name = "main/references.html"

    MODELS = {
        "destination": (Destination, forms.AddDestinationForm, "Направление", "wagon"),
        "tariff": (TariffHistory, forms.AddTariffForm, "Тариф", "trainevent"),
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["destinations"] = Destination.objects.annotate(used=Count("wagon")).order_by("name")
        context["tariffs"] = TariffHistory.objects.annotate(used=Count("trainevent")).order_by("-start_date")
        current = TariffHistory.for_date(timezone.localdate())
        context["current_tariff_id"] = current.pk if current else None
        context.update(reference_forms())
        return context

    def post(self, request, *args, **kwargs):
        # action_type вида "add_destination", "edit_tariff", "delete_destination"...
        verb, _, kind = (request.POST.get("action_type") or "").partition("_")
        if kind not in self.MODELS or verb not in ("add", "edit", "delete"):
            messages.error(request, "Неизвестное действие.")
            return redirect_back(request, "references")

        model, form_class, title, relation = self.MODELS[kind]
        if verb == "add":
            return save_form(request, form_class(request.POST), f"{title} добавлен{'о' if kind == 'destination' else ''}")

        obj = get_object_or_404(model, pk=request.POST.get("object_id") or 0)
        if verb == "edit":
            return save_form(request, form_class(request.POST, instance=obj), f"{title}: изменения сохранены")

        used = getattr(obj, f"{relation}_set").count()
        if used:
            messages.error(request, f"Нельзя удалить «{obj}»: используется в {used} записях.")
        else:
            obj.delete()
            messages.success(request, f"{title} удалён{'о' if kind == 'destination' else ''}")
        return redirect_back(request, "references")


class DeleteWagonView(LoginRequiredMixin, View):
    def post(self, request, pk):
        get_object_or_404(Wagon, pk=pk).delete()
        messages.success(request, "Вагон удалён")
        return redirect_back(request)


class DeleteEventView(LoginRequiredMixin, View):
    def post(self, request, pk):
        get_object_or_404(TrainEvent, pk=pk).delete()
        messages.success(request, "Событие удалено")
        return redirect_back(request)
