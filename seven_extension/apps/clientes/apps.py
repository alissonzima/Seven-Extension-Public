from django.apps import AppConfig


class ClientesConfig(AppConfig):
    """
    Configuração da aplicação Django para o aplicativo 'clientes'.

    Attributes:
        default_auto_field (str): O campo automático padrão para modelos.
        name (str): O nome do aplicativo.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.clientes'
