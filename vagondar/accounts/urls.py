from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .forms import CustomLoginForm

urlpatterns = [
    path('login/', LoginView.as_view(
        template_name="accounts/login_page.html",
        authentication_form=CustomLoginForm,
        redirect_authenticated_user=True,
    ), name="login"),
    path('logout/', LogoutView.as_view(next_page="login"), name='logout'),
    path('profile/', views.ProfileView.as_view(), name="profile"),
    path('profile/download/', views.download_db, name="download_db"),
]
