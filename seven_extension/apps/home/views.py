import json

from apps.clientes.methods import (
    get_context_data,
    printl,
    retorna_clientes,
    retorna_mapa,
)
from django import template
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.serializers import serialize
from django.db.models.fields.related import ForeignKey
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template import loader
from django.urls import reverse


def serialize_with_foreign_keys(obj):
    """
    Serializa um objeto Django com suporte a chaves estrangeiras.

    Args:
        obj: Objeto Django a ser serializado.

    Returns:
        dict: Dicionário contendo os dados serializados do objeto.

    Notas:
        - Utiliza o método `serialize` do Django para gerar uma representação JSON do objeto.
        - Para cada campo de chave estrangeira no objeto, serializa o valor correspondente.
        - Adiciona manualmente um campo 'tem_credencial' ao objeto serializado.

    Exemplo:
        - serialize_with_foreign_keys(instancia_do_objeto)
    """
    data = json.loads(serialize('json', [obj]))[0]

    # Itera sobre os campos do objeto
    for field in obj._meta.fields:
        if isinstance(field, ForeignKey):
            # Serializa o valor do campo de chave estrangeira
            data['fields'][field.name] = serialize(
                'json', [getattr(obj, field.name)]
            )

    # Adiciona o campo 'tem_credencial' ao objeto serializado
    data['fields']['tem_credencial'] = getattr(obj, 'tem_credencial', None)

    return data


@login_required(login_url='/login/')
def index(request):
    """
    View para a página inicial.

    Args:
        request: Objeto HttpRequest contendo os detalhes da solicitação.

    Returns:
        HttpResponse: Resposta HTTP renderizada para a página inicial.

    Notas:
        - Requer autenticação do usuário, redirecionando para a página de login se não autenticado.
        - Carrega dados do contexto usando a função get_context_data.
        - Serializa os clientes usando a função serialize_with_foreign_keys.
        - Analisa o campo 'inverter' para cada cliente.
        - Renderiza o template 'home/index.html' ou 'home/overview.html' com base no tipo de usuário.

    """
    context = get_context_data(request)

    # Verifica se o usuário não é um cliente
    if context['user_type'] != 'cliente':
        context['segment'] = 'index'

        # Obtém clientes com informações sobre energia hoje e energia total
        if context.get('user_empresa'):
            (
                clientes,
                context['all_energy_today'],
                context['all_energy_total'],
            ) = retorna_clientes(context['user_empresa'])
        else:
            (
                clientes,
                context['all_energy_today'],
                context['all_energy_total'],
            ) = retorna_clientes('admin')

        # Obtém dados do mapa para os clientes
        context['mapa'] = retorna_mapa(clientes)

        # Serializa os clientes, incluindo chaves estrangeiras
        clientes_serializados = [
            serialize_with_foreign_keys(cliente) for cliente in clientes
        ]

        # Analisa o campo 'inverter' para cada cliente
        for cliente in clientes_serializados:
            if cliente['fields']['inverter']:
                cliente['fields']['inverter'] = json.loads(
                    cliente['fields']['inverter']
                )[0]['fields']

        # Converte os clientes serializados em formato JSON
        context['clientes'] = json.dumps(clientes_serializados)
        context['width'] = 45
        html_template = loader.get_template('home/index.html')
    else:
        context['segment'] = 'overview'
        html_template = loader.get_template('home/overview.html')

    # Renderiza o template com o contexto e retorna uma resposta HTTP
    return HttpResponse(html_template.render(context, request))


@login_required(login_url='/login/')
def pages(request):
    """
    View para renderizar páginas dinâmicas.

    Args:
        request: Objeto HttpRequest contendo os detalhes da solicitação.

    Returns:
        HttpResponse: Resposta HTTP renderizada para a página solicitada.

    Notas:
        - Requer autenticação do usuário, redirecionando para a página de login se não autenticado.
        - Carrega dados do contexto usando a função get_context_data.
        - Obtém o ID do cliente se a solicitação for um POST.
        - Redireciona para a página de administração se a URL contiver 'admin'.
        - Renderiza o template correspondente com base no nome da página fornecido na URL.
        - Manipula exceções para templates não encontrados e outros erros, exibindo páginas de erro.

    """
    context = get_context_data(request)

    # Obtém o ID do cliente se a solicitação for um POST
    if request.method == 'POST':
        context['client_id'] = request.POST.get('dashboard-cliente-id')

    # Define o ID do cliente com base no tipo de usuário
    if request.user_type not in ['admin', 'integrador']:
        context['client_id'] = request.user.cliente.id

    try:
        # Obtém o nome do arquivo HTML da URL
        load_template = request.path.split('/')[-1]

        # Redireciona para a página de administração
        if load_template == 'admin':
            return HttpResponseRedirect(reverse('admin:index'))
        # Define o template para a página de visão geral
        elif load_template == 'overview':
            load_template = 'overview.html'

        # Define o segmento no contexto com base no nome do arquivo HTML
        context['segment'] = load_template

        # Carrega o template HTML correspondente
        html_template = loader.get_template('home/' + load_template)
        return HttpResponse(html_template.render(context, request))

    # Manipula exceção se o template não for encontrado
    except template.TemplateDoesNotExist:
        html_template = loader.get_template('home/page-404.html')
        return HttpResponse(html_template.render(context, request))

    # Manipula exceção genérica e exibe uma página de erro
    except Exception as e:
        printl('Erro encontrado', e)
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render(context, request))
