from django.http import HttpResponseForbidden
from django.shortcuts import render


class TipoUsuarioMiddleware:
    """
    Middleware para adicionar informações relacionadas ao tipo de usuário à solicitação.

    Este middleware adiciona atributos à solicitação, como `user_type`, `user_empresa`,
    `user_cliente`, `user_id` e `username` com base no usuário autenticado.

    Exemplo:
        ```
        
        # Configure o middleware nas configurações do Django

        # Em views ou outros middlewares, você pode acessar as informações adicionadas assim:
        def minha_view(request):
            print(request.user_type)
            print(request.user_empresa)
            print(request.user_cliente)
            print(request.user_id)
            print(request.username)
        ```
    """

    def __init__(self, get_response):
        """
        Inicializa o middleware.

        Args:
            get_response: Função para obter a resposta da solicitação.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Processa a solicitação, adicionando informações relacionadas ao tipo de usuário.

        Args:
            request (HttpRequest): Objeto HttpRequest associado à solicitação.

        Returns:
            HttpResponse: Resposta da solicitação.
        """
        if request.user.is_authenticated:
            request.user_type = request.user.tipo_usuario.nome_tipo
            # print(request.user.empresa.id)
            if request.user.empresa:
                request.user_empresa = request.user.empresa.id
            else:
                request.user_empresa = None
            if request.user.cliente:
                request.user_cliente = request.user.cliente.id
            else:
                request.user_cliente = None
            request.user_id = request.user.id
            request.username = request.user.username
        else:
            request.user_type = None
        response = self.get_response(request)
        return response


class Custom403Middleware:
    """
    Middleware para substituir a resposta 403 padrão por uma página personalizada.

    Este middleware verifica se a resposta é um HttpResponseForbidden e, se for,
    substitui por uma renderização personalizada da página 403.

    """

    def __init__(self, get_response):
        """
        Inicializa o middleware.

        Args:
            get_response: Função para obter a resposta da solicitação.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Processa a solicitação e substitui a resposta 403 padrão, se necessário.

        Args:
            request (HttpRequest): Objeto HttpRequest associado à solicitação.

        Returns:
            HttpResponse: Resposta da solicitação.
        """
        response = self.get_response(request)
        if isinstance(response, HttpResponseForbidden):
            return render(request, 'home/page-403.html', status=403)
        return response
