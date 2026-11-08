import io

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.http import HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView


@staff_member_required
def download_db(request):
    """Резервная копия всех данных в JSON (работает и с SQLite, и с PostgreSQL).

    Восстановление: python manage.py loaddata <файл>.json
    """
    buffer = io.StringIO()
    call_command(
        "dumpdata",
        "--natural-foreign", "--natural-primary",
        "--exclude=contenttypes", "--exclude=auth.permission",
        "--exclude=admin.logentry", "--exclude=sessions",
        "--indent=2",
        stdout=buffer,
    )
    filename = f"vagondar_backup_{timezone.localtime():%Y-%m-%d_%H-%M}.json"
    response = HttpResponse(buffer.getvalue(), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"
