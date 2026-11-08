"""Экспорт событий в Excel. Один лист = одно событие."""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side

from .calculations import calculate_event

COLUMN_WIDTHS = {
    "A": 4, "B": 39, "C": 4, "D": 13, "E": 10, "F": 21, "G": 12, "H": 12,
    "I": 12, "J": 12, "K": 12, "L": 12, "M": 15, "N": 17, "O": 13,
}
HEADER_MERGES = ["B1:C2", "D1:D2", "E1:E2", "F1:F2", "G1:I2", "J1:J2",
                 "K1:K2", "L1:L2", "M1:M2", "N1:O2"]
HEADERS = {
    "D1": "проезд локомотива (1,5*2)",
    "E1": "Подача",
    "F1": "Подача вагона+локомотив",
    "G1": "Протяженность",
    "J1": "Объем за вагон",
    "K1": "Объем за локомотив",
    "L1": "Итого объем",
    "M1": 'Тариф ТОО "Е.Ж.Д."',
    "N1": "Итого",
}
FIRST_ROW = 3

FONT_HEADER = Font(name="Times New Roman", size=12, bold=True, color="000000")
FONT_BODY = Font(name="Times New Roman", size=12, bold=False, color="000000")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_thin = Side(border_style="thin", color="000000")
BORDER = Border(top=_thin, left=_thin, bottom=_thin, right=_thin)

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def event_title(event):
    return (f"{event.event_date:%d.%m.%Y} "
            f"({event.get_operation_type_display()} {event.event_time:%H:%M})")


def fill_event_sheet(ws, event):
    calc = calculate_event(event)
    rows = [r for r in calc.rows if r.has_destination]
    n = len(rows)
    last_row = FIRST_ROW + n - 1

    for col, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col].width = width
    for rng in HEADER_MERGES:
        ws.merge_cells(rng)

    for col in range(2, 16):
        for row in (1, 2):
            ws.cell(row=row, column=col).border = BORDER
        ws.cell(row=1, column=col).font = FONT_HEADER
        ws.cell(row=1, column=col).alignment = CENTER

    ws["B1"] = event_title(event)
    for cell, text in HEADERS.items():
        ws[cell] = text

    if not n:
        ws.cell(row=FIRST_ROW, column=2, value="Вагонов нет").font = FONT_BODY
        return

    divisor_2 = calc.loko_divisor_2
    tariff = float(calc.tariff) if calc.tariff is not None else None

    for i, item in enumerate(rows):
        r = FIRST_ROW + i
        values = {
            1: i + 1,
            2: f"{item.wagon.destination.name}: {item.wagon.wagon_number}",
            3: 1,
            4: 3,
            5: 1,
            6: f"=C{r}+D{r}*E{r}",
            7: float(item.distance_1),
            8: float(item.distance_2),
            10: f"=SUM(G{r}:I{r})",
            11: f"=D{r}*G{r}/{n}+D{r}*H{r}/{divisor_2}",
            12: f"=SUM(J{r}:K{r})",
            13: tariff,
            14: f"=L{r}*M{r}",
        }
        for col, value in values.items():
            ws.cell(row=r, column=col, value=value)
        for col in (10, 11, 12):
            ws.cell(row=r, column=col).number_format = "0.000"
        ws.cell(row=r, column=14).number_format = "0.00"
        for col in range(1, 16):
            ws.cell(row=r, column=col).font = FONT_BODY
        for col in range(2, 16):
            ws.cell(row=r, column=col).border = BORDER

    total = ws.cell(row=FIRST_ROW, column=15, value=f"=SUM(N{FIRST_ROW}:N{last_row})")
    total.number_format = "0.00"
    total.alignment = CENTER
    if n > 1:
        ws.merge_cells(f"O{FIRST_ROW}:O{last_row}")


def build_workbook(events):
    """Создаёт книгу: по листу на каждое событие. Возвращает bytes."""
    wb = Workbook()
    wb.remove(wb.active)
    for event in events:
        # ':' запрещён в названиях листов, длина <= 31
        title = f"{event.event_date:%d.%m.%Y} {event.event_time:%H-%M}"
        fill_event_sheet(wb.create_sheet(title=title[:31]), event)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
