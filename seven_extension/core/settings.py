import os

from channels.routing import get_default_application
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()
DEBUG = os.getenv('DEBUG') == 'True'

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.getenv('SECRET_KEY')

FERNET_KEYS = os.getenv('FERNET_KEYS')

ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')

ALLOWED_HOSTS = ['*']
X_FRAME_OPTIONS = 'SAMEORIGIN'
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:85',
    'http://127.0.0.1',
    'https://' + os.getenv('SERVER'),
]

AUTH_USER_MODEL = 'clientes.UsuarioCustomizado'


INSTALLED_APPS = [
    'daphne',
    #'debug_toolbar',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.home', 
    'apps.clientes',
    'django_apscheduler',
    'django_plotly_dash.apps.DjangoPlotlyDashConfig',
]

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.user_middleware.TipoUsuarioMiddleware',
    'core.user_middleware.Custom403Middleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django_plotly_dash.middleware.BaseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

AUTHENTICATION_BACKENDS = ['core.user_backend.CustomModelBackend']

INTERNAL_IPS = [
    '127.0.0.1',
]

CORS_ALLOWED_ORIGINS = [
    put_cors_allowed,
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'x-csrftoken',
]

CORS_ALLOW_METHODS = [
    'GET',
    'POST',
]

SCHEDULER_CONFIG = {
    'apscheduler.executors.default': {
        'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
        'max_workers': 2,  # Ajuste este número para o número desejado de threads
    }
}

ROOT_URLCONF = 'core.urls'
LOGIN_REDIRECT_URL = 'home'  # Route defined in home/urls.py
LOGOUT_REDIRECT_URL = 'home'  # Route defined in home/urls.py
TEMPLATE_DIR = os.path.join(
    CORE_DIR, 'apps/templates'
)  # ROOT dir for templates

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATE_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.context_processors.cfg_assets_root',
            ],
        },
    },
]

WSGI_APPLICATION = 'seven_extension.core.wsgi.application'
ASGI_APPLICATION = 'seven_extension.core.asgi.application'

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases
# print(os.environ.get('DB_ENGINE'))

if os.environ.get('DB_ENGINE') and os.environ.get('DB_ENGINE') == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USERNAME'),
            'PASSWORD': os.getenv('DB_PASS'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
        },
    }
# else:
#     DATABASES = {
#         'default': {
#             'ENGINE': 'django.db.backends.sqlite3',
#             'NAME': 'db.sqlite3',
#             'OPTIONS': {
#             'timeout': 20,  # 20 segundos
#             },
#         }
#     }

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'pt-BR'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_L10N = True

USE_TZ = True

#############################################################
# SRC: https://devcenter.heroku.com/articles/django-assets

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATIC_ROOT = os.path.join(CORE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (os.path.join(CORE_DIR, 'apps', 'static'),)

#############################################################
#############################################################

application = get_default_application()
