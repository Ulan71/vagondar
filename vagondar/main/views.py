from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from . import forms
from .calculations import calculate_event
from .excel import XLSX_CONTENT_TYPE, build_workbook
from .models import TariffHistory, TrainEvent, Wagon


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
        "add_destination": (forms.AddDestinationForm, "Направление добавлено"),
        "add_tariff": (forms.AddTariffForm, "Тариф добавлен"),
    }

    def get_queryset(self):
        qs = events_queryset()
        query = (self.request.GET.get("search_events") or "").strip()
        if not query:
            return qs

        found_date = parse_date(query)
        if found_date:
            return qs.filter(event_date=found_date)

        condition = Q(wagons__wagon_number__icontains=query)
        if query.isdigit():
            condition |= Q(id=int(query))
        return qs.filter(condition).distinct()

    def paginate_queryset(self, queryset, page_size):
        # get_page() вместо page(): несуществующая страница -> последняя, а не 404
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["add_wagon_form"] = forms.AddWagonForm()
        context["add_event_form"] = forms.AddEventForm()
        context["add_destination_form"] = forms.AddDestinationForm()
        context["add_tariff_form"] = forms.AddTariffForm()
        context["show_actions"] = True
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
            form = forms.AddWagonForm(request.POST)
            form.instance.event = event
            return self._save(form, "Вагон добавлен")

        if action in self.CREATE_ACTIONS:
            form_class, success = self.CREATE_ACTIONS[action]
            return self._save(form_class(request.POST), success)

        messages.error(request, "Неизвестное действие.")
        return redirect_back(request)

    def _save(self, form, success_message):
        if form.is_valid():
            form.save()
            messages.success(self.request, success_message)
        else:
            messages.error(self.request, f"Не сохранено. {form_errors_text(form)}")
        return redirect_back(self.request)


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


class TariffHistoryViews(LoginRequiredMixin, ListView):
    template_name = "main/tariff_history_page.html"
    context_object_name = "tariffs"

    def get_queryset(self):
        return TariffHistory.objects.order_by("-start_date")


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
