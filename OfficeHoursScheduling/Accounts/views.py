from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm


def login_view(request):
    redirect_to = request.POST.get("next") or request.GET.get("next", "")
    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        login(request, form.user)
        if url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(redirect_to)
        return redirect(getattr(settings, "LOGIN_REDIRECT_URL", "/"))

    return render(
        request,
        "Accounts/login.html",
        {"form": form, "next": redirect_to},
    )
