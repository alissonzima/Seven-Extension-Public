import os

import requests
from apps.authentication.forms import LoginForm, SignUpForm
from apps.clientes.methods import printl
from core.user_backend import CustomModelBackend
from django.contrib.auth import authenticate, login

# Create your views here.
from django.shortcuts import redirect, render
from dotenv import load_dotenv

load_dotenv()


def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None

    if request.method == 'POST':
        if form.is_valid():
            # printl(request.POST['g-recaptcha-response'])

            recaptcha_verify_url = os.getenv('RECAPTCHA_VERIFY_URL')
            recaptcha_secret_key = os.getenv('RECAPTCHA_SECRET_KEY')
            secret_response = request.POST['g-recaptcha-response']

            verify_response = requests.post(
                f'{recaptcha_verify_url}?secret={recaptcha_secret_key}&response={secret_response}'
            ).json()
            printl(verify_response)

            if verify_response['success'] is False:
                return render(request, 'home/page-403.html', status=403)

            username = form.cleaned_data.get('username').strip()
            password = form.cleaned_data.get('password').strip()
            user_type = request.POST[
                'form-login'
            ]  # Este é o valor do campo oculto

            user = CustomModelBackend().authenticate(
                request,
                username=username,
                password=password,
                user_type=user_type,
            )

            if user is not None:
                login(request, user)
                return redirect('/')
            else:
                msg = 'Credenciais ou tipo de login inválido'
        else:
            msg = 'Erro validando o formulário'

    recaptcha_site_key = os.getenv('RECAPTCHA_SITE_KEY')
    return render(
        request,
        'accounts/login.html',
        {'form': form, 'msg': msg, 'recaptcha_site_key': recaptcha_site_key},
    )


def register_user(request):
    msg = None
    success = False

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)

            msg = 'Usuário criado com sucesso.'
            success = True

            # return redirect("/login/")

        else:
            msg = 'Formulário inválido'
    else:
        form = SignUpForm()

    return render(
        request,
        'accounts/register.html',
        {'form': form, 'msg': msg, 'success': success},
    )
