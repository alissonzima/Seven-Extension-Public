from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CustomModelBackend(ModelBackend):
    """
    Backend de autenticação personalizado para lidar com diferentes tipos de usuários.

    Methods:
        authenticate(self, request, username=None, password=None, **kwargs):
            Autentica o usuário com base no nome de usuário, senha e outros parâmetros.

        get_user(self, user_id):
            Obtém um usuário com base no ID do usuário.

    Exemplo:
        ```
        
        from django.contrib.auth import authenticate, login
        from django.contrib.auth.models import User
        from myapp.backends import CustomModelBackend

        # Configure o backend personalizado nas configurações do Django

        # Autenticação usando o backend personalizado
        user = authenticate(request, username='example_user', password='example_password', user_type='cliente')

        if user is not None:
            login(request, user)
            print('Autenticação bem-sucedida!')
        else:
            print('Autenticação falhou.')
        ```
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Autentica o usuário com base no nome de usuário, senha e outros parâmetros.

        Args:
            request (HttpRequest): Objeto HttpRequest associado à solicitação.
            username (str): Nome de usuário fornecido.
            password (str): Senha fornecida.
            **kwargs: Outros parâmetros opcionais para personalizar a autenticação.

        Returns:
            User: Objeto do modelo de usuário autenticado, ou None se a autenticação falhar.
        """
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username=username)

            # Verifique se a solicitação está vindo do painel de administração
            if 'admin' in request.path:
                # Use a autenticação padrão para o painel de administração
                if user.check_password(password):
                    return user
                else:
                    return None

            # Verifique se o tipo de usuário corresponde ao valor do campo oculto
            if (
                user.tipo_usuario.nome_tipo != kwargs.get('user_type')
                and user.tipo_usuario.nome_tipo != 'admin'
            ):
                return None

            # Verifique a senha (você pode querer lidar com senhas inválidas de maneira diferente)
            if user.check_password(password):
                return user

        except UserModel.DoesNotExist:
            return None

    def get_user(self, user_id):
        """
        Obtém um usuário com base no ID do usuário.

        Args:
            user_id (int): ID do usuário.

        Returns:
            User: Objeto do modelo de usuário, ou None se o usuário não for encontrado.
        """
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
