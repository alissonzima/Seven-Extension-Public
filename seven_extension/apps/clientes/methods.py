# from .models import Consumo, Injecao

# from django.db.models import F, Sum, Window, RowNumber, Range
# from django.db.models.functions import TruncMonth

# injecao_pairs = (
#     Injecao.objects.annotate(
#         rank=Window(
#             expression=RowNumber(),
#             partition_by=[F('instalacao')],
#             order_by=F('mes_referencia').asc(),
#         )
#     )
#     .values(
#         'instalacao',
#         'mes_referencia',
#         'consumo_mensal_fora_ponta',
#         'energia_injetada_fora_ponta',
#         'energia_recebida_fora_ponta',
#         'creditos_utilizados_fora_ponta',
#         'saldo_acumulado',
#         'rank',
#     )
#     .alias(
#         prev_mes_referencia=Window(
#             expression=RowNumber(),
#             partition_by=[F('instalacao')],
#             order_by=F('mes_referencia').asc(),
#             frame=Range(start=None, end=-1),
#         )
#     )
# )

# results = (
#     Consumo.objects.select_related('instalacao__cliente')
#     .annotate(
#         plant_name=F('instalacao__cliente__plant_name'),
#         codigo=F('instalacao__codigo'),
#         mes_referencia=F('injecao__mes_referencia'),
#         consumo_mensal_fora_ponta=F('injecao__consumo_mensal_fora_ponta'),
#         energia_injetada_fora_ponta=F('injecao__energia_injetada_fora_ponta'),
#         energia_recebida_fora_ponta=F('injecao__energia_recebida_fora_ponta'),
#         creditos_utilizados_fora_ponta=F('injecao__creditos_utilizados_fora_ponta'),
#         saldo_acumulado=F('injecao__saldo_acumulado'),
#     )
#     .filter(
#         injecao__in=injecao_pairs,
#         mes_ano__month=TruncMonth(F('injecao__mes_referencia')),
#     )
#     .values(
#         'plant_name',
#         'codigo',
#         'mes_referencia',
#         'consumo',
#         'valor',
#         'consumo_mensal_fora_ponta',
#         'energia_injetada_fora_ponta',
#         'energia_recebida_fora_ponta',
#         'creditos_utilizados_fora_ponta',
#         'saldo_acumulado',
#     )
#     .annotate(
#         energystamp_sum_kwh=Sum(F('instalacao__cliente__geracao__energystamp')) / 1000,
#     )
# )

# for result in results:
#     print(result)

import os

import folium
import folium.plugins as plugins
from apps.clientes.models import (
    Cliente,
    CredencialConcessionaria,
    Notificacao,
    RelacaoClienteEmpresa,
)
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.utils import timezone
from dotenv import load_dotenv

import logging
import sys


def get_context_data(request):
    """
    Obtém os dados de contexto para serem utilizados nas views.

    Args:
        request (HttpRequest): O objeto de requisição Django.

    Returns:
        context (dict): Um dicionário contendo os dados de contexto.

    Comentários:
        - Esta função é responsável por preparar os dados de contexto que serão
          utilizados nas views.
        - O tipo de usuário, nome de usuário e outras informações relevantes são
          incluídos no contexto.
        - Notificações são filtradas com base no tipo de usuário e outras
          condições específicas.

    """
    context = {}

    # Adiciona informações básicas ao contexto
    context['user_type'] = request.user_type
    context['username'] = request.username

    # Adiciona o ID do cliente se o usuário não for admin ou integrador
    if request.user_type not in ['admin', 'integrador']:
        context['client_id'] = request.user.cliente.id

    # Adiciona a empresa do usuário, se existir
    if request.user_empresa:
        context['user_empresa'] = request.user_empresa

    # Obtém todas as notificações cuja data final ainda não chegou ou é nula
    notificacoes = Notificacao.objects.filter(
        Q(final_notificacao__gte=timezone.now())
        | Q(final_notificacao__isnull=True),
        Q(local_notificacao='geral') | Q(local_notificacao=request.user_type),
    )

    notificacoes_personalizadas = []

    if request.user_type == 'admin':
        # Admin vê todas as mensagens
        notificacoes_personalizadas = notificacoes
    elif request.user_type == 'integrador':
        # Integrador vê mensagens destinadas a todos, a integradores ou a sua empresa específica
        notificacoes_personalizadas = notificacoes.filter(
            Q(abrangencia_notificacao='todos')
            | Q(
                abrangencia_notificacao='empresa',
                tipo_usuario__nome_tipo='integrador',
                empresa__isnull=True,
            )
            | Q(
                abrangencia_notificacao='empresa',
                tipo_usuario__nome_tipo='integrador',
                empresa=request.user_empresa,
            )
            | Q(
                abrangencia_notificacao='clientes',
                empresa=request.user_empresa,
            )
        )
    elif request.user_type == 'cliente':
        # Cliente vê mensagens destinadas a todos, a clientes ou a ele mesmo
        inversor_cliente = Cliente.objects.get(
            id=request.user_cliente
        ).inverter
        relacao_cliente_empresa = RelacaoClienteEmpresa.objects.filter(
            cliente_id=request.user_cliente
        ).values_list('empresa_id', flat=True)
        notificacoes_personalizadas = notificacoes.filter(
            Q(abrangencia_notificacao='todos')
            | Q(tipo_usuario__nome_tipo='cliente', cliente__isnull=True)
            | Q(
                tipo_usuario__nome_tipo='cliente', cliente=request.user_cliente
            )
            | Q(
                abrangencia_notificacao='clientes',
                empresa_id__in=relacao_cliente_empresa,
            )
            | Q(abrangencia_notificacao='todos', inversor=inversor_cliente)
        )

    context['notificacoes_personalizadas'] = notificacoes_personalizadas

    return context


def retorna_clientes(user_empresa):
    """
    Retorna informações dos clientes e totais de energia.

    Args:
        user_empresa (str): O identificador da empresa do usuário.

    Returns:
        clientes (seven_extension.apps.clientes.models.Cliente): Um objeto contendo os clientes.
        all_energy_today (float): Energia gerada por um cliente hoje.
        all_energy_total (float): Energia total gerada por um cliente.

    Comentários:
        - Esta função retorna informações formatadas dos clientes e totais de energia,
          considerando as credenciais associadas.
        - O parâmetro 'user_empresa' é utilizado para filtrar os clientes com base
          na empresa do usuário.
        - A energia total do dia e a energia total acumulada são agregadas e formatadas.
        - A função retorna uma tupla contendo a lista de clientes, energia total do dia
          e energia total acumulada.

    """
    printl('user empresa', user_empresa)

    # Inicializa variáveis para cálculos totais de energia
    all_energy_today = 0
    all_energy_total = 0

    # Obtém todos os clientes ordenados por nome da planta
    clientes = Cliente.objects.all().order_by('plant_name')

    # Filtra clientes com base na empresa do usuário, exceto para usuários 'admin'
    if user_empresa != 'admin':
        clientes = clientes.filter(relacaoclienteempresa__empresa=user_empresa)

    # Prefetch credenciais associadas aos clientes para evitar consultas adicionais
    clientes = clientes.order_by('plant_name').prefetch_related(
        Prefetch(
            'credencialconcessionaria_set',
            queryset=CredencialConcessionaria.objects.all(),
            to_attr='credenciais',
        )
    )

    # Itera sobre cada cliente para processar informações e calcular totais
    for cliente in clientes:
        # Adiciona energia do dia e energia total aos totais
        all_energy_today += float(cliente.energy_today)
        all_energy_total += float(cliente.energy_total)

        # Formata e converte a energia do dia para exibição
        if cliente.energy_today != 0:
            cliente.energy_today = (
                '{:,.2f}'.format(float(cliente.energy_today) / 1000)
                .replace(',', 'x')
                .replace('.', ',')
                .replace('x', '.')
            )
        # Formata e converte a energia total para exibição
        if cliente.energy_total != 0:
            cliente.energy_total = (
                '{:,.2f}'.format(float(cliente.energy_total) / 1000)
                .replace(',', 'x')
                .replace('.', ',')
                .replace('x', '.')
            )

        # Verifica se o cliente tem credenciais associadas
        tem_credencial = any(cliente.credenciais)
        cliente.tem_credencial = tem_credencial

    # Formata e converte os totais de energia para exibição
    all_energy_today = (
        '{:,.2f}'.format(float(all_energy_today) / 1000)
        .replace(',', 'x')
        .replace('.', ',')
        .replace('x', '.')
    )
    all_energy_total = (
        '{:,.0f}'.format(float(all_energy_total) / 1000 / 1000)
        .replace(',', 'x')
        .replace('.', ',')
        .replace('x', '.')
    )

    # Retorna a tupla com informações dos clientes e totais de energia
    return clientes, all_energy_today, all_energy_total


def retorna_mapa(plants):
    """
    Cria e retorna um mapa interativo usando a biblioteca Folium.

    Args:
        plants (QuerySet): Um QuerySet contendo informações das plantas.

    Returns:
        seven (str): Uma representação HTML do mapa interativo.

    Comentários:
        - Esta função recebe informações sobre as plantas e gera um mapa interativo
          usando a biblioteca Folium.
        - O mapa é centrado nas coordenadas fornecidas (latitude e longitude).
        - Marcadores coloridos são adicionados para cada planta com base na energia
          do dia e energia total.
        - Um botão de tela cheia é adicionado ao canto superior direito do mapa.
        - Uma legenda é adicionada no canto inferior esquerdo do mapa, explicando as cores
          dos marcadores.

    """
    # Coordenadas para centralizar o mapa
    latitude = insert_latitude
    longitude = insert_longitude

    # Cria um mapa Folium
    seven = folium.Map(location=[latitude, longitude], zoom_start=6)

    # Adiciona o botão de tela cheia ao mapa
    plugins.Fullscreen(
        position='topright',
        title='Expandir',
        title_cancel='Sair',
        force_separate_button=True,
    ).add_to(seven)

    # Itera sobre cada planta e adiciona marcadores ao mapa
    for plant in plants:
        # Define a cor do marcador com base na energia do dia e energia total
        if plant.energy_today == 0 and plant.energy_total == 0:
            color = 'red'
        elif plant.energy_today == 0:
            color = 'orange'
        else:
            color = 'green'

        # Cria um ícone Folium com a cor definida
        icon = folium.Icon(color=color)
        # Obtém a localização da planta (latitude, longitude)
        location = (plant.latitude, plant.longitude)

        # Adiciona um marcador ao mapa com o ícone e popup contendo o nome da planta
        folium.Marker(
            location=location, icon=icon, popup=plant.plant_name
        ).add_to(seven)

    # Adiciona uma legenda personalizada ao mapa
    legenda_html = """
    <div style="position: fixed; 
        bottom: 10px; 
        left: 10px; 
        width: 100px; 
        height: 60px; 
        border:2px solid grey; 
        z-index:9999; 
        font-size:10px;
        background: rgba(169, 169, 169, 0.5);"> <!-- Adicionando fundo cinza esmaecido -->
    &nbsp;<b>Legenda</b><br>
    &nbsp;<i class="fa fa-map-marker fa-1x" style="color:green"></i>&nbsp;Online<br>
    &nbsp;<i class="fa fa-map-marker fa-1x" style="color:orange"></i>&nbsp;Sem comunicação<br>
    &nbsp;<i class="fa fa-map-marker fa-1x" style="color:red"></i>&nbsp;Nunca comunicou
    </div>
    """
    seven.get_root().html.add_child(folium.Element(legenda_html))

    # Retorna a representação HTML do mapa
    return seven._repr_html_()


def printl(*args):
    """
    Função de impressão condicional usada para depurar em ambientes de teste.

    Args:
        *args: Argumentos variáveis a serem impressos.

    Comentários:
        - Esta função verifica se o ambiente é 'test' antes de imprimir os argumentos.
        - Útil para depuração, pois evita imprimir mensagens desnecessárias em produção.

    Exemplo:
        printl('Mensagem de depuração')  # A mensagem será impressa apenas se AMBIENTE for 'test'.
    """
    load_dotenv()
    if os.getenv('AMBIENTE') == 'test':
        print(*args)


def setup_debug_logging():
    """
    Configura o logger para enviar mensagens para o syslog com nível de depuração.
    """
    # Configurando o logger para enviar mensagens para o syslog
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Definindo um manipulador para enviar mensagens para o syslog
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    # Definindo o formato das mensagens de log
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Adicionando o manipulador ao logger
    logger.addHandler(handler)

def print_debug(message):
    """
    Método para imprimir mensagens de depuração.
    """
    # Configuração do logger se ainda não estiver configurado
    if not logging.getLogger().handlers:
        setup_debug_logging()
    
    logger = logging.getLogger()
    logger.debug(message)
