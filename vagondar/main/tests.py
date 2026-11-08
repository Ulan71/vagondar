import io
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .calculations import calculate_event
from .models import Destination, TariffHistory, TrainEvent, Wagon


class BaseData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("operator", password="pass12345")
        cls.tariff_old = TariffHistory.objects.create(start_date=date(2025, 1, 1), tariff=Decimal("10000"))
        cls.tariff = TariffHistory.objects.create(start_date=date(2025, 8, 1), tariff=Decimal("15000"))
        cls.near = Destination.objects.create(name="Ближний", distance_km=Decimal("0.3"))
        cls.far = Destination.objects.create(name="Дальний", distance_km=Decimal("0.5"))
        cls.event = TrainEvent.objects.create(
            operation_type="arrival", event_date=date(2025, 8, 10), event_time=time(9, 30), tariff=cls.tariff,
        )
        Wagon.objects.create(wagon_number="111", event=cls.event, destination=cls.near)
        Wagon.objects.create(wagon_number="222", event=cls.event, destination=cls.far)

    def login(self):
        self.client.login(username="operator", password="pass12345")


class CalculationTests(BaseData):
    def test_two_wagons(self):
        calc = calculate_event(self.event)
        near, far = calc.rows
        # общий участок 0.3 делится на 2 вагона, индивидуальный 0.2 — на (2 - 1)
        self.assertEqual(near.distance_1, Decimal("0.3"))
        self.assertEqual(near.distance_2, Decimal("0"))
        self.assertEqual(far.distance_2, Decimal("0.2"))
        self.assertEqual(near.total_vol, Decimal("0.3") + Decimal("0.45"))
        self.assertEqual(far.total_vol, Decimal("0.5") + Decimal("0.45") + Decimal("0.6"))
        self.assertEqual(calc.total_price, (near.total_vol + far.total_vol) * 15000)

    def test_single_wagon(self):
        event = TrainEvent.objects.create(operation_type="removal", event_date=date(2025, 8, 11),
                                          event_time=time(10, 0), tariff=self.tariff)
        Wagon.objects.create(wagon_number="333", event=event, destination=self.far)
        calc = calculate_event(event)
        self.assertEqual(calc.total_vol, Decimal("0.5") * 4)

    def test_no_wagons(self):
        event = TrainEvent.objects.create(operation_type="removal", event_date=date(2025, 8, 11),
                                          event_time=time(10, 0), tariff=self.tariff)
        calc = calculate_event(event)
        self.assertEqual(calc.total_vol, 0)
        self.assertEqual(calc.total_price, 0)

    def test_wagon_without_destination_is_skipped(self):
        Wagon.objects.create(wagon_number="999", event=self.event, destination=None)
        calc = calculate_event(self.event)
        self.assertEqual(calc.skipped_wagons, 1)
        self.assertEqual(calc.wagons_count, 2)
        self.assertEqual(calc.total_price, calculate_event(self.event, [
            w for w in self.event.wagons.all() if w.destination]).total_price)

    def test_event_without_tariff(self):
        self.event.tariff = None
        calc = calculate_event(self.event)
        self.assertIsNone(calc.total_price)


class TariffAutoSelectTests(BaseData):
    def test_tariff_picked_by_date(self):
        e1 = TrainEvent.objects.create(operation_type="arrival", event_date=date(2025, 3, 1), event_time=time(8, 0))
        e2 = TrainEvent.objects.create(operation_type="arrival", event_date=date(2025, 9, 1), event_time=time(8, 0))
        self.assertEqual(e1.tariff, self.tariff_old)
        self.assertEqual(e2.tariff, self.tariff)

    def test_no_tariff_before_first(self):
        e = TrainEvent.objects.create(operation_type="arrival", event_date=date(2024, 1, 1), event_time=time(8, 0))
        self.assertIsNone(e.tariff)


class AccessTests(BaseData):
    def test_pages_require_login(self):
        for url in [reverse("main"), reverse("tariff_history"), reverse("profile"),
                    reverse("export_event", args=[self.event.pk]), reverse("export_period")]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse("login"), response["Location"])

    def test_delete_requires_login(self):
        self.client.post(reverse("delete_event", args=[self.event.pk]))
        self.assertTrue(TrainEvent.objects.filter(pk=self.event.pk).exists())

    def test_db_backup_only_for_staff(self):
        self.login()
        self.assertEqual(self.client.get(reverse("download_db")).status_code, 302)
        User.objects.filter(pk=self.user.pk).update(is_staff=True)
        response = self.client.get(reverse("download_db"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"wagon_number": "111"', response.content)


class MainPageTests(BaseData):
    def setUp(self):
        self.login()

    def test_index_renders(self):
        response = self.client.get(reverse("main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Дальний")

    def test_index_survives_broken_data(self):
        Wagon.objects.create(wagon_number="777", event=self.event, destination=None)
        TrainEvent.objects.create(operation_type="arrival", event_date=date(2024, 1, 1), event_time=time(8, 0))
        response = self.client.get(reverse("main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "нет направления")

    def test_bad_page_number(self):
        self.assertEqual(self.client.get(reverse("main") + "?page=999").status_code, 200)

    def test_search(self):
        other = TrainEvent.objects.create(operation_type="removal", event_date=date(2025, 8, 20),
                                          event_time=time(8, 0), tariff=self.tariff)
        Wagon.objects.create(wagon_number="55500", event=other, destination=self.near)
        events = lambda q: list(self.client.get(reverse("main"), {"search_events": q}).context["events"])
        self.assertEqual(events("555"), [other])
        self.assertEqual(events("10.08.2025"), [self.event])
        self.assertEqual(events("2025-08-20"), [other])

    def test_add_event_with_auto_tariff(self):
        response = self.client.post(reverse("main"), {
            "action_type": "add_event", "operation_type": "removal",
            "event_date": "2025-08-15", "event_time": "12:00", "tariff": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TrainEvent.objects.get(event_date=date(2025, 8, 15)).tariff, self.tariff)

    def test_invalid_form_does_not_crash(self):
        response = self.client.post(reverse("main"), {"action_type": "add_event", "operation_type": "x"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Не сохранено")

    def test_unknown_action_does_not_crash(self):
        response = self.client.post(reverse("main"), {"action_type": "hack"}, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_add_wagon_to_missing_event(self):
        response = self.client.post(reverse("main"), {"action_type": "add_wagon", "event_id": "",
                                                      "wagon_number": "1", "destination": self.near.pk})
        self.assertEqual(response.status_code, 404)

    def test_add_and_edit_wagon(self):
        self.client.post(reverse("main"), {"action_type": "add_wagon", "event_id": self.event.pk,
                                           "wagon_number": "444", "destination": self.near.pk})
        wagon = Wagon.objects.get(wagon_number="444")
        self.assertEqual(wagon.event, self.event)
        self.client.post(reverse("main"), {"action_type": "edit_wagon", "wagon_id": wagon.pk,
                                           "wagon_number": "445", "destination": self.far.pk})
        wagon.refresh_from_db()
        self.assertEqual((wagon.wagon_number, wagon.destination, wagon.event), ("445", self.far, self.event))

    def test_negative_distance_rejected(self):
        self.client.post(reverse("main"), {"action_type": "add_destination", "name": "X", "distance_km": "-1"})
        self.assertFalse(Destination.objects.filter(name="X").exists())

    def test_delete_event(self):
        self.client.post(reverse("delete_event", args=[self.event.pk]))
        self.assertFalse(TrainEvent.objects.filter(pk=self.event.pk).exists())


class ExcelExportTests(BaseData):
    def setUp(self):
        self.login()

    def load(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        return load_workbook(io.BytesIO(response.content))

    def test_single_event(self):
        wb = self.load(self.client.get(reverse("export_event", args=[self.event.pk])))
        ws = wb.active
        self.assertEqual(ws["B1"].value, "10.08.2025 (Пригон 09:30)")
        self.assertEqual(ws["B3"].value, "Ближний: 111")
        self.assertEqual(ws["F4"].value, "=C4+D4*E4")  # раньше во всех строках было C3+D3*E3
        self.assertEqual(ws["K4"].value, "=D4*G4/2+D4*H4/1")
        self.assertEqual(ws["O3"].value, "=SUM(N3:N4)")
        self.assertEqual(ws["M3"].value, 15000)

    def test_period_each_sheet_has_own_header(self):
        empty = TrainEvent.objects.create(operation_type="arrival", event_date=date(2025, 8, 12),
                                          event_time=time(14, 0), tariff=self.tariff)
        wb = self.load(self.client.get(reverse("export_period"), {
            "start_date": "2025-08-01", "end_date": "2025-08-31", "operation_type": "arrival"}))
        self.assertEqual(len(wb.worksheets), 2)  # без пустого листа «Sheet»
        self.assertEqual(wb.worksheets[0]["B1"].value, "10.08.2025 (Пригон 09:30)")
        self.assertEqual(wb.worksheets[1]["B1"].value, "12.08.2025 (Пригон 14:00)")
        self.assertEqual(wb.worksheets[1]["B3"].value, "Вагонов нет")
        self.assertTrue(empty)

    def test_period_without_events(self):
        response = self.client.get(reverse("export_period"), {"start_date": "2020-01-01", "end_date": "2020-01-31"},
                                   follow=True)
        self.assertContains(response, "событий нет")

    def test_period_without_dates(self):
        response = self.client.get(reverse("export_period"), follow=True)
        self.assertContains(response, "Укажите")
