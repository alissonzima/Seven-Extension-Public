import calendar
import datetime
import locale
from datetime import timedelta
from time import sleep
from urllib.parse import urljoin  # Importe a função urljoin

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import pytz
import requests
from apps.clientes.methods import printl
from apps.clientes.models import (
    Cliente,
    Geracao,
    GeracaoDiaria,
    UsuarioCustomizado,
)
from dash import dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash_bootstrap_templates import load_figure_template
from dash_dangerously_set_inner_html import DangerouslySetInnerHTML
from django.contrib.sessions.models import Session
from django.urls import reverse  # Importe a função reverse
from django.utils.timezone import get_current_timezone, make_aware
from django_plotly_dash import DjangoDash

# Defina a configuração regional para 'pt_BR.UTF-8'
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

# Crie um aplicativo DjangoDash para renderizar a dashboard
app = DjangoDash(
    'geracao_clientes',
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    external_scripts=[
        'https://cdn.plot.ly/plotly-basic-1.54.3.min.js',
    ],
)


# Obtenha o número total de dias no mês atual
year = datetime.date.today().year
month = datetime.date.today().month
num_days = calendar.monthrange(year, month)[1]

# Crie as opções para seleção de dias no mês
day_options = [{'label': str(i), 'value': i} for i in range(1, num_days + 1)]

# Obtenha todos os clientes da base de dados
# clientes = Cliente.objects.all()
clientes = []

# Criação do layout do app
app.layout = html.Div(
    id='parent-dash-div',
    children=[
        DangerouslySetInnerHTML(
            """
            <style>
                .custom-date-picker .DateInput_input {
                    font-size: 12px !important;
                    height: 20px !important;
                }
                .user-select-none.svg-container {
                    width: 100% !important;
                }
                @media (min-width: 768px) {
                    .col-md-auto.custom-dropdown-container {
                        padding-right: 5px;
                    }
                }
                .row-dropdown-container {
                    margin-bottom: 0;
                    margin-right: 5px;
                }

                @media (max-width: 885px) {
                    .row-dropdown-container {
                        margin-bottom: 10px;
                    }
                    .main-svg {
                        padding-top: 35px;
                    }
                    .custom-dropdown-container {
                        margin-left: 1px;
                        max-width: 100px;
                    }
                    .client-selector-button {
                        margin-left: 11px;
                    }
                    .button-group-time {
                        margin-top: -25px !important;
                    }
                    .custom-range-container {
                        margin-top: 33px !important;
                        right: 52px !important;
                    }
                }
                @media (max-width: 450px) {
                    .Select-control {
                        width: 73.5px !important;
                    }
                    .custom-dropdown-container {
                        width: 73.5px !important;
                    }
                    #custom-range-button {
                        width: 85px !important;
                    }
                    .progress-bar-label {
                        display: none;
                    }
                }

                #graph-container {
                    height: 500px;
                    position: relative;
                    width: 100%;
                    display: flex;
                }
                #energy-generation-graph {
                    width: 100%;
                }
                .button-dropdown-container {
                    position: absolute;
                    top: 2%;
                    left: 2%;
                    z-index: 1;
                    display: flex;
                    align-items: center;
                    flex-wrap: wrap;
                }
                .button-group-time {
                    margin-top: -16px;
                }
                .client-filter-input {
                    color: #000;
                    background-color: #fff;
                }

                .client-selector-list-container {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background-color: #2C394B;
                    border-radius: 15px;
                    border: 1px solid #ccc;
                    padding: 20px;
                    z-index: 1051;
                    color: #fff;
                }
                #client-selector-backdrop {
                    position: fixed !important;
                    top: 0 !important;
                    left: 0 !important;
                    width: 100% !important;
                    height: 100% !important;
                    background-color: rgba(0, 0, 0, 0.5); /* Cor de fundo preta com opacidade de 50% */
                    z-index: 1050;
                }
                .dark-theme .Select-menu-outer {
                    background-color: #0f2537; /* Define a cor de fundo para o tema dark */
                    border-color: #0f2537; /* Define a cor da borda para o tema dark */
                    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.06); /* Define a sombra para o tema dark */
                    /* Adicione outras propriedades de estilo personalizadas conforme necessário */
                }
                .dark-theme .Select-control {
                    background-color: #0f2537 !important;
                    color: #fff !important;
                }
                .dark-theme .has-value.Select--single>.Select-control .Select-value .Select-value-label,
                .dark-theme .has-value.is-pseudo-focused.Select--single>.Select-control .Select-value .Select-value-label {
                    color: #e1e1e1 !important; /* Define a cor da fonte como branco */
                }
                #modal-cliente-title {
                    color: #fff;
                }
                .lightning-symbol {
                    align-items: center;
                    width: 100%;
                }
                @media (min-width: 450px) {
                    .mobile-only {
                        display: none !important;
                    }
                }
            </style>
        """
        ),
        dcc.Store(id='store_resize'),
        html.Button('', id='resize_button', style={'display': 'none'}),
        html.Div(id='dummy', style={'display': 'none'}),
        dcc.Store(id='theme-store'),
        dcc.Input(id='hidden-input', type='hidden', value=''),
        html.Div(id='output-screen', hidden='hidden'),
        html.Button(id='hidden-resize', style={'display': 'none'}),
        html.Button('', id='dark-theme-button', style={'display': 'none'}),
        html.Button('', id='light-theme-button', style={'display': 'none'}),
        html.Div(
            id='graph-selectors-container',
            style={'display': 'flex', 'align-items': 'center'},
            children=[
                html.Div(
                    id='graph-container',
                    className='graph-container',
                    children=[
                        html.Div(
                            id='graph-div',
                            style={'display': 'flex', 'flex-grow': '1'},
                            children=[
                                dcc.Graph(
                                    id='energy-generation-graph',
                                    figure={
                                        'data': [],
                                        'layout': {
                                            'xaxis': {'title': ''},
                                            'yaxis': {'title': ''},
                                            'autosize': True,
                                        },
                                    },
                                    config={
                                        'displayModeBar': False,
                                        'displaylogo': False,
                                        'responsive': True,
                                    },
                                    style={
                                        'pointer-events': 'none',
                                    },
                                ),
                            ],
                        ),
                        html.Div(
                            id='month-year-container',
                            className='button-dropdown-container',
                            children=[
                                html.Div(
                                    className='row flex-md-row row-dropdown-container d-flex align-items-center justify-content-flex-start',
                                    children=[
                                        html.Div(
                                            id='search-client-button',
                                            className='col-4 col-md-auto custom-dropdown-container',
                                            children=[
                                                html.Button(
                                                    children=html.Span(
                                                        html.I(
                                                            className='feather icon-user-plus'
                                                        )
                                                    ),
                                                    id='open-client-selector',
                                                    className='btn btn-secondary btn-date client-selector-button ',
                                                    style={
                                                        'position': 'relative',
                                                        'top': '2.7px',
                                                        'height': '36px',
                                                    },
                                                ),
                                            ],
                                            style={
                                                'padding-left': '0',
                                                'padding-right': '0',
                                                'max-width': '42px',
                                            },
                                        ),
                                        html.Div(
                                            className='col-4 col-md-auto custom-dropdown-container',
                                            children=[
                                                dcc.Dropdown(
                                                    id='day-selector',
                                                    options=day_options,
                                                    value=datetime.date.today().day,
                                                    clearable=False,
                                                    searchable=False,
                                                    placeholder='Selecione o dia',
                                                    className='custom-dropdown',
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className='col-4 col-md-auto custom-dropdown-container',
                                            children=[
                                                dcc.Dropdown(
                                                    id='month-selector',
                                                    options=[
                                                        {
                                                            'label': calendar.month_name[
                                                                i
                                                            ],
                                                            'value': i,
                                                        }
                                                        for i in range(1, 13)
                                                    ],
                                                    value=datetime.date.today().month,
                                                    clearable=False,
                                                    searchable=False,
                                                    placeholder='Selecione o mês',
                                                    className='custom-dropdown',
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className='col-4 col-md-auto custom-dropdown-container',
                                            children=[
                                                dcc.Dropdown(
                                                    id='year-selector',
                                                    options=[
                                                        {
                                                            'label': str(i),
                                                            'value': i,
                                                        }
                                                        for i in range(
                                                            2015,
                                                            datetime.date.today().year
                                                            + 1,
                                                        )
                                                    ],
                                                    value=datetime.date.today().year,
                                                    clearable=False,
                                                    searchable=False,
                                                    placeholder='Selecione o ano',
                                                    className='custom-dropdown',
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className='row mt-3 flex-md-row button-group-row',
                                    children=[
                                        html.Div(
                                            className='col-12 col-md-auto button-group-time',
                                            children=[
                                                html.Div(
                                                    id='client-selector-button-container',
                                                    className='custom-button-group',
                                                    children=[
                                                        html.Div(
                                                            id='client-selector-container',
                                                            style={
                                                                'display': 'none'
                                                            },  # Inicialmente oculto
                                                            children=[
                                                                html.Div(
                                                                    className='client-selector-backdrop',
                                                                    id='client-selector-backdrop',
                                                                    style={
                                                                        'display': 'none'
                                                                    },  # Inicialmente oculto
                                                                ),
                                                                html.Div(
                                                                    className='client-selector-list-container',
                                                                    children=[
                                                                        html.H5(
                                                                            'Selecionar cliente(s):',
                                                                            className='modal-title',
                                                                            id='modal-cliente-title',
                                                                        ),  # Adicionado className "modal-title"
                                                                        dbc.InputGroup(
                                                                            [
                                                                                dbc.Input(
                                                                                    id='client-filter-input',
                                                                                    type='text',
                                                                                    placeholder='Buscar cliente...',
                                                                                    className='form-control',  # Substituído o className para "form-control"
                                                                                ),
                                                                                dbc.Button(
                                                                                    id='clear-selection-button',
                                                                                    color='secondary',
                                                                                    className='btn btn-secondary',
                                                                                    children=html.Span(
                                                                                        html.I(
                                                                                            className='feather icon-user-x'
                                                                                        )
                                                                                    ),
                                                                                ),
                                                                            ]
                                                                        ),
                                                                        html.Div(
                                                                            className='client-selector-list',
                                                                            style={
                                                                                'max-height': '200px',
                                                                                'overflow-y': 'scroll',
                                                                                'min-width': '275px',
                                                                            },  # Limita a altura e adiciona a barra de rolagem
                                                                            children=[
                                                                                dcc.Checklist(
                                                                                    id='client-selector',
                                                                                    options=[
                                                                                        {
                                                                                            'label': cliente.plant_name,
                                                                                            'value': cliente.id,
                                                                                        }
                                                                                        for cliente in clientes
                                                                                    ],
                                                                                    value=[
                                                                                        # clientes.first().plant_name
                                                                                    ],  # Substitua o .first() pelo valor padrão desejado
                                                                                    labelStyle={
                                                                                        'display': 'block'
                                                                                    },  # Exibir checkboxes em blocos
                                                                                    className='list-group',  # Adicionado className "list-group"
                                                                                ),
                                                                            ],
                                                                        ),
                                                                        html.Button(
                                                                            'Fechar',
                                                                            id='close-client-selector',
                                                                            className='btn btn-secondary',
                                                                        ),
                                                                    ],
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            id='output-container'
                                                        ),
                                                    ],
                                                ),
                                                dbc.ButtonGroup(
                                                    [
                                                        dbc.Button(
                                                            'Dia',
                                                            id='day-button',
                                                            className='btn-date btn',
                                                            n_clicks=0,
                                                            size='sm',
                                                            color='secondary',
                                                        ),
                                                        dbc.Button(
                                                            'Mês',
                                                            id='month-button',
                                                            className='btn-date btn',
                                                            n_clicks=0,
                                                            size='sm',
                                                            color='secondary',
                                                        ),
                                                        dbc.Button(
                                                            'Ano',
                                                            id='year-button',
                                                            className='btn-date btn',
                                                            n_clicks=0,
                                                            size='sm',
                                                            color='secondary',
                                                        ),
                                                        dbc.Button(
                                                            'Total',
                                                            id='total-button',
                                                            className='btn-date btn',
                                                            n_clicks=0,
                                                            size='sm',
                                                            color='secondary',
                                                        ),
                                                        html.Button(
                                                            'Período Personalizado',
                                                            id='custom-range-button',
                                                            n_clicks=0,
                                                            className='btn-date btn btn-sm',
                                                            style={
                                                                'margin-left': '10px',
                                                                'margin-right': '10px',
                                                                'white-space': 'nowrap',
                                                                'width': '165px',
                                                                'padding': '0.25rem 0.5rem',
                                                            },
                                                        ),
                                                    ],
                                                    className='button-group-container custom-button-group',
                                                    id='button-group-container',
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className='col-12 col-md-auto',
                                            children=[
                                                html.Div(
                                                    id='custom-range-container',
                                                    className='custom-range-container',
                                                    style={
                                                        'display': 'none',
                                                        'position': 'absolute',
                                                        'margin-top': '60px',
                                                        'right': '75px',
                                                    },
                                                    children=[
                                                        html.Div(
                                                            className='inputs-wrapper',
                                                            style={
                                                                'position': 'relative',
                                                                'left': '15px',
                                                                'margin-top': '-30px',
                                                            },
                                                            children=[
                                                                dcc.DatePickerRange(
                                                                    id='date-range-picker',
                                                                    display_format='DD/MM/YYYY',
                                                                    start_date_placeholder_text='Data Inicial',
                                                                    end_date_placeholder_text='Data Final',
                                                                    className='custom-date-picker',
                                                                    style={
                                                                        'width': '150px'
                                                                    },
                                                                    with_portal=True,  # ou with_full_screen_portal=True
                                                                ),
                                                                html.Div(
                                                                    style={
                                                                        'display': 'flex',
                                                                        'align-items': 'center',
                                                                        'justify-content': 'space-between',
                                                                    },
                                                                    children=[
                                                                        html.Button(
                                                                            'Aplicar',
                                                                            id='apply-button',
                                                                            n_clicks=0,
                                                                            className='btn btn-secondary btn-sm',
                                                                            style={
                                                                                'margin-top': '10px',
                                                                                'margin-right': '5px',
                                                                            },
                                                                        ),
                                                                        html.Button(
                                                                            'Cancelar',
                                                                            id='cancel-button',
                                                                            n_clicks=0,
                                                                            className='btn btn-secondary btn-sm',
                                                                            style={
                                                                                'margin-top': '10px',
                                                                                'margin-right': '0px',
                                                                                'margin-left': 'auto',
                                                                            },
                                                                        ),
                                                                    ],
                                                                ),
                                                            ],
                                                        )
                                                    ],
                                                )
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        ),
        dcc.Store(id='selected-date-range', storage_type='memory'),
        # Elemento oculto para armazenar o tipo de usuário
        dcc.Store(
            id='user-type-store',
            data={'user_type': None, 'client_id': None, 'user_empresa': None},
        ),
        html.Div(id='user-type', style={'display': 'none'}),
        html.Div(id='output-div', style={'display': 'none'}),
        html.Div(id='dummy-input', style={'display': 'none'}),
        html.Div(id='selected-clients-ids', style={'display': 'none'}),
    ],
    style={'font-family': 'Arial, sans-serif'},
)


@app.callback(
    Output('selected-clients-ids', 'children'),
    Input('client-selector', 'value'),
)
def update_selected_clients_ids(selected_clients):
    """
    Atualiza a exibição dos IDs dos clientes selecionados.

    Esta função é um callback para a atualização dinâmica da exibição dos IDs dos clientes selecionados.
    O resultado é utilizado para atualizar o conteúdo do elemento HTML com o id 'selected-clients-ids'.

    Args:
        selected_clients (list): Lista dos IDs dos clientes selecionados.

    Returns:
        (str): Uma string contendo os IDs dos clientes selecionados, separados por vírgula.

    """
    return ','.join(map(str, selected_clients))


app.clientside_callback(
    """
    function(value) {
        // Esta função captura informações do usuário e as retorna como um dicionário.

        // Adicione um ouvinte de evento para o evento DOMContentLoaded
        document.addEventListener('DOMContentLoaded', function() {
            // Obtenha a data atual
            var today = new Date();
            var day = today.getDate();
            var month = today.getMonth() + 1;  // Os meses são indexados a partir de 0 em JavaScript
            var year = today.getFullYear();

            // Atualize os valores dos dropdowns
            document.getElementById('day-selector').setAttribute('value', day);
            document.getElementById('month-selector').setAttribute('value', month);
            document.getElementById('year-selector').setAttribute('value', year);
        });

        // Obtenha o tipo de usuário do atributo de dados 'data-user-type' do corpo do documento
        var userType = document.body.getAttribute('data-user-type');
        
        // Obtenha o ID do cliente do atributo de dados 'client-id' do corpo do documento
        var clientId = document.body.getAttribute('client-id');
        
        // Obtenha a empresa do usuário do atributo de dados 'user-empresa' do corpo do documento
        var userEmpresa = document.body.getAttribute('user-empresa');
        
        // Retorna um dicionário contendo as informações capturadas.
        return {'user_type': userType, 'client_id': clientId, 'user_empresa': userEmpresa};
    }
    """,
    Output('user-type-store', 'data'),  # Atualize o valor do Store
    Input('dummy-input', 'children'),
)


app.clientside_callback(
    """
    function(n_clicks, dummy) {
        // Esta função manipula eventos de redimensionamento da janela e retorna a largura atual da janela.

        // Adiciona um ouvinte de evento de redimensionamento que simula um clique no botão de redimensionamento.
        window.addEventListener('resize', function() {
            document.getElementById('resize_button').click();
        });

        // Obtém os gatilhos dos eventos que acionaram a chamada de retorno.
        let triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);

        // Verifica se o evento foi acionado pelo componente 'dummy' ou pelo botão de redimensionamento.
        if (triggered.includes('dummy.children')) {
            // Se acionado pelo componente 'dummy', retorna a largura atual da janela.
            return window.innerWidth;
        } else if (triggered.includes('resize_button.n_clicks')) {
            // Se acionado pelo botão de redimensionamento, retorna a largura atual da janela.
            return window.innerWidth;
        }
    }
    """,
    Output('store_resize', 'data'),
    [Input('resize_button', 'n_clicks'), Input('dummy', 'children')],
)


@app.callback(
    Output('client-selector-container', 'style'),
    Output('client-selector-backdrop', 'style'),
    [
        Input('open-client-selector', 'n_clicks'),
        Input('close-client-selector', 'n_clicks'),
    ],
    [
        State('client-selector-container', 'style'),
        State('client-selector-backdrop', 'style'),
    ],
)
def toggle_client_selector(n_open, n_close, container_style, backdrop_style):
    """
    Esta função controla a exibição e ocultação do seletor de clientes.

    Parameters:
        n_open (int): O número de cliques no botão 'open-client-selector'.
        n_close (int): O número de cliques no botão 'close-client-selector'.
        container_style (dict): O estilo atual do contêiner do seletor de clientes.
        backdrop_style (dict): O estilo atual do fundo do seletor de clientes.

    Returns:
        (dict): O estilo atualizado do contêiner do seletor de clientes.
        (dict): O estilo atualizado do fundo do seletor de clientes.
    """
    if n_open and (not n_close or n_open > n_close):
        # Se o botão 'open-client-selector' foi clicado mais recentemente do que o botão 'close-client-selector',
        # atualiza os estilos para exibir o seletor de clientes e o fundo.
        updated_container_style = container_style.copy()
        updated_container_style['display'] = 'block'  # Exibir o seletor de clientes
        updated_backdrop_style = backdrop_style.copy()
        updated_backdrop_style['display'] = 'block'  # Exibir o fundo
        return updated_container_style, updated_backdrop_style
    else:
        # Se o botão 'close-client-selector' foi clicado mais recentemente ou ambos não foram clicados,
        # atualiza os estilos para ocultar o seletor de clientes e o fundo.
        return {'display': 'none'}, {'display': 'none'}


@app.callback(
    Output(
        'theme-store', 'data'
    ),  # Atualize a propriedade data/value do componente intermediário
    [
        Input('dark-theme-button', 'n_clicks_timestamp'),
        Input('light-theme-button', 'n_clicks_timestamp'),
    ],
)
def update_theme(dark_ts, light_ts):
    """
    Atualiza o tema do aplicativo com base no botão de tema clicado mais recentemente.

    Parameters:
        dark_ts (int): Timestamp do último clique no botão de tema escuro.
        light_ts (int): Timestamp do último clique no botão de tema claro.

    Returns:
        (str): O tema atual ('dark' se o botão de tema escuro foi clicado mais recentemente, 'light' se o botão de tema claro foi clicado mais recentemente, None se nenhum botão foi clicado ainda).
    """
    # Determine qual é o tema atual com base em qual botão foi clicado por último
    if dark_ts is not None and (light_ts is None or dark_ts > light_ts):
        return 'dark'
    elif light_ts is not None and (dark_ts is None or light_ts > dark_ts):
        return 'light'
    else:
        return None  # Nenhum botão foi clicado ainda


@app.callback(
    Output('client-selector', 'value'),
    Output('client-filter-input', 'value'),
    Input('clear-selection-button', 'n_clicks'),
    prevent_initial_call=True,
)
def clear_selection(n_clicks):
    """
    Limpa a seleção de clientes e o valor do filtro quando o botão 'clear-selection-button' é clicado.

    Parameters:
        n_clicks (int): O número de cliques no botão 'clear-selection-button'.

    Returns:
        Tuple (list, str): Uma tupla contendo uma lista vazia (seleção de clientes) e uma string vazia (valor do filtro).
    """
    if n_clicks is None:
        raise PreventUpdate

    return [], ''


@app.callback(
    Output('client-selector', 'options'),  # Define a saída como as opções do seletor de clientes
    Input('client-filter-input', 'value'),  # Recebe o valor do filtro do usuário
    Input('user-type-store', 'data'),  # Recebe os dados armazenados sobre o tipo de usuário
)
def update_client_options(filter_value, user_type_store_data):
    """
    Atualiza as opções disponíveis para o seletor de clientes com base no valor do filtro e no tipo de usuário.

    Parameters:
        filter_value (str): O valor do filtro inserido pelo usuário.
        user_type_store_data (dict): Os dados armazenados sobre o tipo de usuário.

    Returns:
        unique_options (list): Uma lista de opções para o seletor de clientes.
    """
    # Obtém o tipo de usuário a partir dos dados armazenados
    user_type = user_type_store_data['user_type']

    # Se o tipo de usuário não estiver disponível, interrompe a execução
    if user_type is None:
        raise PreventUpdate

    # Obtém informações adicionais do usuário
    user_empresa = user_type_store_data['user_empresa']
    client_id = user_type_store_data['client_id']

    # Filtra os clientes com base no tipo de usuário
    if user_type != 'cliente':
        if user_empresa:
            clientes_filtro = Cliente.objects.filter(
                relacaoclienteempresa__empresa=user_empresa
            )
        else:
            clientes_filtro = Cliente.objects.all()
    else:
        clientes_filtro = Cliente.objects.filter(id=client_id)

    # Trata o caso em que o valor do filtro é nulo
    if filter_value is None:
        filter_value = ''

    # Cria uma lista de opções com base nos clientes filtrados
    options = [
        {'label': cliente.plant_name, 'value': cliente.id}
        for cliente in clientes_filtro
    ]

    # Filtra as opções com base no valor do filtro
    filtered_options = [
        option
        for option in options
        if filter_value.lower() in option['label'].lower()
    ]

    # Remove duplicatas mantendo a primeira ocorrência de cada rótulo
    unique_options = list(
        {option['label']: option for option in filtered_options}.values()
    )

    return unique_options


app.clientside_callback(
    """
    function(value) { 
    
        var graficos = {};
    
        $(document).ready(function() {
            log('TESTE DE CARREGAMENTO DE ARQUIVO JS');
            var lastContent = $('#selected-clients-ids').text();

            // Escute as mudanças na div oculta selected-clients-ids
            $('#selected-clients-ids').on('DOMSubtreeModified', function() {
                
                var currentContent = $(this).text();
                
                if (currentContent !== lastContent) {
                
                    // debug
                    // log('DOMSubtreeModified event triggered');
                    //log('New content:', $(this).text());
                    
                    // Recupere o valor da div e divida em uma lista de IDs
                    var selectedClientsString = $(this).text();
                    var selectedClientsArray = selectedClientsString.split(',');

                    // Converta a lista de IDs de volta para inteiros
                    var selectedClients = selectedClientsArray.map(function(id) {
                        return parseInt(id, 10);
                    });

                    log("Clientes selecionados:", selectedClients);

                    // Enviar a seleção de clientes para o endpoint do Django
                    enviarClienteParaDjango(selectedClients);
                    
                    lastContent = currentContent;
                }
            });
            
            // Verifique se o valor de data-user-type é 'cliente'
            var userType = $('body').attr('data-user-type');
            if (userType === 'cliente') {
                // Se for cliente, defina a opacidade do botão como 0 para torná-lo invisível
                // e a propriedade pointer-events como none para desativar os eventos de clique
                $('#search-client-button').css({
                    'opacity': 0,
                    'pointer-events': 'none'
                });
            }
            
            var clientID = $('body').attr('client-id');
            // Recupere todos os clientes selecionados
            var selectedClients = [parseInt(clientID, 10)]; // Converta para inteiro
            log("selected inicial" + selectedClients);

            // Enviar a seleção de clientes para o endpoint do Django
            enviarClienteParaDjango(selectedClients);
            $('.progress-bar').addClass('progress-bar-animated');
        });

        function enviarClienteParaDjango(selectedClients) {
            
            // Obter o host do navegador (como http://localhost:8000 ou o URL do ngrok)
            var host = window.location.origin;
            
            // Verificar se o host contém 'localhost'
            if (host.includes('localhost')) {
                // Se contiver 'localhost', combinar o host com a porta do servidor Django
                host = host + ':8000';
            }

            var urlDjangoBase = "/clientes/atualizar_tab";  // Substitua pelo endpoint do Django
            var urlDjango = host + urlDjangoBase;

            // Recuperar o token CSRF dos cookies
            var csrftoken = getCookie('csrftoken');
        

            $.ajax({
                url: urlDjango,
                type: "POST",
                data: JSON.stringify(selectedClients),
                dataType: "json",
                contentType: "application/json",
                headers: {
                    "X-CSRFToken": csrftoken  // Incluir o token CSRF nos headers
                },
                success: function(data) {
                    
                    log("Resposta do Django: ", data);
                    var info = data['info'];
                    log("Info: ", info);
                    delete data['info'];
                    if ('previsao' in data) {
                        var previsao = data['previsao'];
                        log("Previsao: ", previsao);
                        delete data['previsao'];
                    }
                    
                    // Remover a mensagem de erro da interface do usuário (se existir)
                    const elementoAcaoNecessaria = document.querySelector('[name="analise_conta_tab"] > h6');
                    if (elementoAcaoNecessaria) {
                        elementoAcaoNecessaria.remove();
                    }
                        
                    // Verificar se o retorno do AJAX é um dicionário vazio
                    if (jQuery.isEmptyObject(data)) {
                        
                        log("Vazio");
                        
                        // Desabilitar todas as abas
                        $('#myTab .nav-link').addClass('disabled');

                        // Selecionar a primeira aba
                        $('#myTab .nav-item:not(.dropdown) .nav-link:first').removeClass('disabled').tab('show');

                        // Remover todos os elementos de dentro da primeira aba
                        $('#consumo').empty();

                        // Escrever "Dados não encontrados" no meio da primeira aba
                        $('#consumo').append('<p class="text-center">Dados não encontrados</p>');
                        
                    } else {
                        
                        // Criar um novo elemento h6
                        const h6 = document.createElement('h6');
                        
                        if (info['problema'] === true) {
                            h6.textContent = info['acao_necessaria'];
                        }


                        // Se o elemento h6 tem algum conteúdo, adicione-o à interface do usuário
                        if (h6.textContent) {
                            h6.style.cssText = 'color: #FF0000 !important;';
                            document.querySelector('[name="analise_conta_tab"]').appendChild(h6);
                        }
 
    
                        if (Object.keys(data).length > 1) {
                            
                            // Crie uma nova variável para armazenar o dicionário reordenado
                            var sortedData = {};

                            // Percorra o dicionário original para separar a instalação 'Geradora'
                            var geradoraData = {};
                            
                            
                            for (var key in data) {
                                if (key.includes('Geradora')) {
                                    geradoraData[key] = data[key];
                                } else {
                                    sortedData[key] = data[key];
                                }
                            }

                            // Combine o dicionário reordenado com a instalação 'Geradora' no final
                            for (var key in geradoraData) {
                                sortedData[key] = geradoraData[key];
                            }
                            
                            // Finalmente, atribua o dicionário reordenado a 'data'
                            data = sortedData;
                            
                            $('#consumo-dropdown .dropdown-menu').empty();
                            $('#injecao-dropdown .dropdown-menu').empty();
                            $('#faturado-dropdown .dropdown-menu').empty();

                            for (let key in data) {
                                let item = $('<li></li>');
                                let link = $('<a class="dropdown-item" href="javascript:"></a>');
                                link.text(key);
                                item.append(link);
                                $('#consumo-dropdown .dropdown-menu').append(item);
                            }

                            for (let key in data) {
                                let item = $('<li></li>');
                                let link = $('<a class="dropdown-item" href="javascript:"></a>');
                                link.text(key);
                                item.append(link);
                                // Verificar se a chave contém a palavra "Beneficiada"
                                if (key.includes('Beneficiada')) {
                                    // Se contiver, adicionar a classe 'disabled' ao item
                                    link.addClass('disabled');
                                }
                                $('#injecao-dropdown .dropdown-menu').append(item);
                            }

                            for (let key in data) {
                                let item = $('<li></li>');
                                let link = $('<a class="dropdown-item" href="javascript:"></a>');
                                link.text(key);
                                item.append(link);
                                $('#faturado-dropdown .dropdown-menu').append(item);
                            }

                            $('#consumo-tab').hide();
                            $('#consumo-dropdown').show();

                            $('#injecao-tab').hide();
                            $('#injecao-dropdown').show();

                            $('#faturado-tab').hide();
                            $('#faturado-dropdown').show();

                            // Adicione um evento de clique aos itens do dropdown
                            $('#consumo-dropdown .dropdown-menu').on('click', 'li', function() {
                                
                                // Obtenha o texto do item do dropdown clicado
                                var codigo = $(this).text();
                                
                                $('#consumo-texto-dinamico').text(codigo);

                                // Verifique se o código existe nos dados
                                if (data.hasOwnProperty(codigo)) {
                                    // Obtenha os dados da instalação
                                    var instalacao = data[codigo];

                                    log('Teste: ' + codigo)
                                    if (codigo.includes('Beneficiada')) {
                                        if ($('#flexSwitchCheckDefault').is(':checked')) {
                                            $('#flexSwitchCheckDefault').click(); // Desmarcar o switch
                                        }
                                        $('#flexSwitchCheckDefault').prop('disabled', true); // Desabilitar o switch
                                    } else {
                                        $('#flexSwitchCheckDefault').prop('disabled', false); // Habilitar o switch
                                    }


                                    // Atualize os progress bars
                                    $.each(instalacao, function(index, item) {
                                        $('.progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);
                                        $('.progress-container:eq(' + index + ') .progress-bar')
                                            .css('width', item.percent + '%')
                                            .attr('aria-valuenow', item.percent);
                                        $('.progress-container:eq(' + index + ') .progress-label').text(item.consumo + ' kWh');
                                    });

                                    $('#consumo-tab').tab('show');
                                    $('.progress-bar').addClass('progress-bar-animated');
                                }
                            });

                            // Adicione um evento de clique aos itens do dropdown
                            $('#injecao-dropdown .dropdown-menu').on('click', 'li', function() {
                                
                                // Verifique se o item do dropdown está desabilitado
                                if (!$(this).find('a').hasClass('disabled')) {
                                    
                                    // Obtenha o texto do item do dropdown clicado
                                    var codigo = $(this).text();
                                    
                                    $('#injecao-texto-dinamico').text(codigo);

                                    // Verifique se o código existe nos dados
                                    if (data.hasOwnProperty(codigo)) {
                                        // Obtenha os dados da instalação
                                        var instalacao = data[codigo];

                                        // Atualize os progress bars
                                        $.each(instalacao, function(index, item) {
                                            $('#injecao .progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);
                                            $('#injecao .progress-container:eq(' + index + ') .progress-bar')
                                                .css('width', item.percent_inject + '%')
                                                .attr('aria-valuenow', item.percent_inject);
                                            $('#injecao .progress-container:eq(' + index + ') .progress-label').text(item.energia_injetada_fora_ponta + ' kWh');
                                        });

                                        // Ative a tab
                                        $('#injecao-tab').tab('show');
                                        $('.progress-bar').addClass('progress-bar-animated');
                                    }
                                }
                            });

                            // Adicione um evento de clique aos itens do dropdown
                            $('#faturado-dropdown .dropdown-menu').on('click', 'li', function() {
                                // Obtenha o texto do item do dropdown clicado
                                var codigo = $(this).text();
                                
                                // Atualizar o texto no elemento com ID "faturado-texto-dinamico"
                                $('#faturado-texto-dinamico').text(codigo);

                                // Verifique se o código existe nos dados
                                if (data.hasOwnProperty(codigo)) {
                                    // Obtenha os dados da instalação
                                    var instalacao = data[codigo];

                                    // Atualize os progress bars
                                    $.each(instalacao, function(index, item) {
                                        $('#faturado .progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);
                                        $('#faturado .progress-container:eq(' + index + ') .progress-bar')
                                            .css('width', item.percent_valor + '%')
                                            .attr('aria-valuenow', item.percent_valor);
                                        $('#faturado .progress-container:eq(' + index + ') .valor').text('R$ ' + item.valor);
                                        $('#faturado .progress-container:eq(' + index + ') .energia').text((item.energia_faturada_fora_ponta > 0 ? Math.round(item.energia_faturada_fora_ponta) : 0) + ' kWh');
                                    });

                                    // Ative a tab
                                    $('#faturado-tab').tab('show');
                                    $('.progress-bar').addClass('progress-bar-animated');
                                }
                            });

                        } else {
                            $('#consumo-tab').show();
                            $('#consumo-dropdown').hide();

                            $('#injecao-tab').show();
                            $('#injecao-dropdown').hide();

                            $('#faturado-tab').show();
                            $('#faturado-dropdown').hide();

                        }
                        
                        var dataAtual = new Date();
                        
                        if ((info['problema'] === true) && (info['key_error'] === 'falta_leitura')) {
                            // Subtrai 1 do mês atual para obter o mês anterior
                            dataAtual.setMonth(dataAtual.getMonth() - 1);
                        }
                        
                        var mesAtual = dataAtual.getMonth() + 1;  // getMonth() retorna um valor de 0 (para janeiro) a 11 (para dezembro), então adicionamos 1 para obter o mês como um número de 1 a 12
                        var anoAtual = dataAtual.getFullYear();

                        // Formate o mês para ter sempre dois dígitos
                        if (mesAtual < 10) {
                            mesAtual = '0' + mesAtual;
                        }

                        var mesAnoAtual = mesAtual + '/' + anoAtual;

                        // Para obter o mês do ano passado, subtraia 1 do ano atual
                        var mesAnoPassado = mesAtual + '/' + (anoAtual - 1);
                        
                        var consumoAtual = 0;
                        var consumoAnoPassado = 0;

                        $.each(data, function(instalacao, detalhes) {
                            $.each(detalhes, function(index, detalhe) {
                                var consumo = parseFloat(detalhe.consumo_total);
                                log('consumo_total ' + consumo + ' mes_ano ' + detalhe.mes_ano + ' mesAnoAtual ' + mesAnoAtual);
                                if (isNaN(consumo)) {
                                    log('Valor inválido para consumo_total: ' + detalhe.consumo_total);
                                    return;
                                }
                                if (detalhe.mes_ano === mesAnoAtual) {
                                    consumoAtual += consumo;
                                } else if (detalhe.mes_ano === mesAnoPassado) {
                                    consumoAnoPassado += consumo;
                                }
                            });
                        });
                        
                        log('Mês atual: ' + mesAnoAtual);
                        log('Mês do ano passado: ' + mesAnoPassado);

                        log('Consumo atual: ' + consumoAtual);
                        log('Consumo ano passado: ' + consumoAnoPassado);

                        // Cálculo da diferença entre os consumos
                        var diferencaConsumo = consumoAnoPassado - consumoAtual;
                        
                        if (diferencaConsumo < 0) {
                            diferencaConsumo = Math.abs(diferencaConsumo);
                        }

                        // Calcular o aumento percentual
                        var aumentoPercentual = (diferencaConsumo / consumoAnoPassado) * 100;
                        
                        log('Aumento percentual: ' + aumentoPercentual);

                        var elemento = $('#analise-consumo');

                        if (consumoAtual < consumoAnoPassado) {
                            elemento.removeClass().addClass('list-group-item bg-success text-white');
                            var texto = `Seu consumo total reduziu em média ${diferencaConsumo.toFixed(2)} kWh em comparação com o mesmo período do ano passado.`;
                            var iconeClass = 'feather icon-zap me-3 text-white';
                        } else if (consumoAtual === consumoAnoPassado) {
                            elemento.removeClass().addClass('list-group-item bg-success text-white');
                            var texto = 'Seu consumo é o mesmo em comparação com o mesmo período do ano passado.';
                            var iconeClass = 'feather icon-zap me-3 text-white';
                        } else if (aumentoPercentual <= 15) {
                            elemento.removeClass().addClass('list-group-item bg-warning');
                            var texto = `Seu consumo aumentou em média ${diferencaConsumo.toFixed(2)} kWh em comparação com o mesmo período do ano passado.`;
                            var iconeClass = 'feather icon-zap me-3 text-dark'; // Mantém o ícone preto
                        } else {
                            elemento.removeClass().addClass('list-group-item bg-danger text-white');
                            var texto = `Atenção, seu consumo está ${diferencaConsumo.toFixed(2)} kWh maior em comparação com o mesmo período do ano passado.`;
                            var iconeClass = 'feather icon-zap me-3 text-white';
                        }

                        // Atualizar o texto e ícone do elemento
                        elemento.html(`<i class="${iconeClass}"></i> ${texto}`)
                        
                        var valorAtual = 0;
                        var valorAnoPassado = 0;

                        $.each(data, function(instalacao, detalhes) {
                            $.each(detalhes, function(index, detalhe) {
                                var valor = parseFloat(detalhe.valor);
                                if (isNaN(valor)) {
                                    log('Valor inválido para valor: ' + detalhe.valor);
                                    return;
                                }
                                if (detalhe.mes_ano === mesAnoAtual) {
                                    valorAtual += valor;
                                } else if (detalhe.mes_ano === mesAnoPassado) {
                                    valorAnoPassado += valor;
                                }
                            });
                        });

                        log('Valor atual: ' + valorAtual.toFixed(2));
                        log('Valor ano passado: ' + valorAnoPassado.toFixed(2));
                        
                        // Cálculo da diferença entre os valores
                        var diferencaValor = valorAtual - valorAnoPassado; // Alterei a ordem para calcular a redução

                        // Calcular o aumento percentual
                        var aumentoPercentualValor = (diferencaValor / valorAnoPassado) * 100;

                        var elementoValor = $('#analise-valor'); // Substitua pelo seletor do seu elemento

                        if (valorAtual < valorAnoPassado) {
                            elementoValor.removeClass().addClass('list-group-item bg-success text-white');
                            var textoValor = `Sua conta de energia reduziu R$ ${Math.abs(diferencaValor).toFixed(2)} em comparação com o mesmo período do ano passado.`;
                            var iconeClassValor = 'feather icon-check me-3 text-white';
                        } else if (valorAtual === valorAnoPassado) {
                            elementoValor.removeClass().addClass('list-group-item bg-success text-white');
                            var textoValor = 'Sua conta de energia está igual ao mesmo período do ano passado.';
                            var iconeClassValor = 'feather icon-check me-3 text-white';
                        } else if (aumentoPercentualValor <= 15) {
                            elementoValor.removeClass().addClass('list-group-item bg-warning');
                            var textoValor = `Sua conta de energia aumentou R$ ${diferencaValor.toFixed(2)} em comparação com o mesmo período do ano passado.`;
                            var iconeClassValor = 'feather icon-check me-3 text-dark'; // Mantém o ícone preto
                        } else {
                            elementoValor.removeClass().addClass('list-group-item bg-danger text-white');
                            var textoValor = `Sua conta de energia aumentou R$ ${Math.abs(diferencaValor).toFixed(2)} em comparação com o mesmo período do ano passado. Fique atento.`;
                            var iconeClassValor = 'feather icon-eye me-3 text-white';
                        }

                        // Atualizar o texto e ícone do elemento
                        elementoValor.html(`<i class="${iconeClassValor}"></i> ${textoValor}`);

                        var mensagens = [];

                        for (var codigo in data) {
                            var detalhes = data[codigo];
                            var saldoAcumuladoAtual = 0;
                            $.each(detalhes, function(index, detalhe) {
                                if (detalhe.mes_ano === mesAnoAtual && detalhe.saldo_acumulado) {
                                    saldoAcumuladoAtual += parseFloat(detalhe.saldo_acumulado);
                                }
                            });
                            var mensagem = 'A instalação ' + codigo + ' tem ' + saldoAcumuladoAtual.toFixed(2) + ' kWh de créditos acumulados.';
                            mensagens.push(mensagem);
                        }

                        log('mensagens ' + mensagens);
                        
                        var elementoCredito = $('#analise-credito'); // Substitua pelo seletor do seu elemento

                        var mensagemHtml = mensagens.map(mensagem => `<i class="feather icon-info me-3 text-dark"></i> ${mensagem}`).join('<br>');

                        elementoCredito.removeClass().addClass('list-group-item bg-info text-black');

                        // Atualizar o texto do elemento com as mensagens
                        elementoCredito.html(mensagemHtml);

                        var consumoInicialProjeto;

                        for (var codigo in data) {
                            var detalhes = data[codigo];
                            for (var i = 0; i < detalhes.length; i++) {
                                if (detalhes[i].consumo_inicial_projeto !== undefined) {
                                    consumoInicialProjeto = detalhes[i].consumo_inicial_projeto;
                                    break;
                                }
                            }
                            if (consumoInicialProjeto !== undefined) break;
                        }

                        log('Consumo inicial do projeto: ' + consumoInicialProjeto);
                        
                        // Crie uma lista dos últimos 12 meses (ou menos)
                        var meses = [];
                        for (var i = 0; i < 12; i++) {
                            var dataAtual = new Date();
                            dataAtual.setMonth(dataAtual.getMonth() - i);
                            var mes = dataAtual.getMonth() + 1;
                            var ano = dataAtual.getFullYear();
                            if (mes < 10) mes = '0' + mes;
                            meses.push(mes + '/' + ano);
                        }

                        var somaConsumo = 0;
                        var contadorMeses = 0;

                        // Crie um objeto para armazenar o consumo total para cada mês
                        var consumoPorMes = {};

                        $.each(data, function(instalacao, detalhes) {
                            $.each(detalhes, function(index, detalhe) {
                                // Verifique se o mês do detalhe está dentro dos últimos 12 meses
                                if (meses.includes(detalhe.mes_ano)) {
                                    var consumo = parseFloat(detalhe.consumo_total);
                                    if (consumoPorMes[detalhe.mes_ano]) {
                                        consumoPorMes[detalhe.mes_ano] += consumo;
                                    } else {
                                        consumoPorMes[detalhe.mes_ano] = consumo;
                                    }
                                }
                            });
                        });
                        
                        // Seleciona o elemento pelo id
                        var itemMesReferencia = document.getElementById('item-mes-referencia');

                        // Altera o conteúdo de texto do elemento
                        itemMesReferencia.innerHTML = '<i class="feather icon-calendar me-3 text-black"></i> Mês referência para análise: <b>' + mesAnoAtual + '</b>';

                        // Calcule a média do consumo total
                        var somaConsumo = 0;
                        $.each(consumoPorMes, function(mes, consumo) {
                            somaConsumo += consumo;
                        });
                        var consumoMedioAnual = somaConsumo / Object.keys(consumoPorMes).length;
                        
                        log('Soma consumo: ' + somaConsumo.toFixed(2));
                        log('Consumo médio anual atualizado: ' + consumoMedioAnual.toFixed(2));

                        var elementoConsumoOriginal = $('#analise-consumo-original');
                        var elementoContainer = $('#analise-container');

                        var porcentagemConsumoAtual = ((consumoAtual - consumoInicialProjeto) / consumoInicialProjeto) * 100;
                        var porcentagemConsumoMedioAnual = ((consumoMedioAnual - consumoInicialProjeto) / consumoInicialProjeto) * 100;

                        var mensagemConsumoOriginal = `A geração média original para a qual seu sistema foi projetado era de <b>${consumoInicialProjeto.toFixed(2)} kWh</b>.`;

                        var classeBgConsumoOriginal = 'bg-light';
                        var classeBgConsumoMensal = porcentagemConsumoAtual > porcentagemConsumoMedioAnual ? 'bg-danger' : 'bg-warning';
                        var classeBgConsumoAnual = porcentagemConsumoMedioAnual > porcentagemConsumoAtual ? 'bg-danger' : 'bg-warning';
                        var textColorConsumoMensal = 'text-black';
                        var textColorConsumoAnual = 'text-black';
                        var textCondicionalConsumoMensal = 'mais';
                        var textCondicionalConsumoAnual = 'mais';
                        var classeIconConsumoMensal = 'icon-alert-triangle'
                        var classeIconConsumoAnual = 'icon-alert-triangle'

                        log('consumoAtual: ' + consumoAtual);
                        log('consumoInicialProjeto: ' + consumoInicialProjeto);
                        log('consumoMedioAnual: ' + consumoMedioAnual);
                        // #TODO: Aqui está duplicado, alterar.
                        if (consumoAtual < consumoInicialProjeto) {
                            classeBgConsumoMensal = 'bg-success';
                            textColorConsumoMensal = 'text-white';
                            textCondicionalConsumoMensal = 'menos';
                            classeIconConsumoMensal = 'icon-check-circle'
                        }

                        if (consumoMedioAnual < consumoInicialProjeto) {
                            classeBgConsumoAnual = 'bg-success';
                            textColorConsumoAnual = 'text-white';
                            textCondicionalConsumoAnual = 'menos';
                            classeIconConsumoAnual = 'icon-check-circle'
                        }

                        // Verificação adicional
                        if (consumoAtual < consumoInicialProjeto && consumoMedioAnual > consumoInicialProjeto) {
                            classeBgConsumoMensal = 'bg-success';
                            textColorConsumoMensal = 'text-white';
                            textCondicionalConsumoMensal = 'menos';
                            classeBgConsumoAnual = 'bg-warning';
                            textColorConsumoAnual = 'text-black';
                            textCondicionalConsumoAnual = 'mais';
                        } else if (consumoMedioAnual < consumoInicialProjeto && consumoAtual > consumoInicialProjeto) {
                            classeBgConsumoMensal = 'bg-warning';
                            textColorConsumoMensal = 'text-black';
                            textCondicionalConsumoMensal = 'mais';
                            classeBgConsumoAnual = 'bg-success';
                            textColorConsumoAnual = 'text-white';
                            textCondicionalConsumoAnual = 'menos';
                        }
                        
                        // Agora que as classes foram definidas, crie os elementos
                        var mensagemConsumoMensal = `Esse mês, você consumiu <b>${consumoAtual.toFixed(2)} kWh</b>. Isso representa <b>${Math.abs(porcentagemConsumoAtual.toFixed(2))}%</b> a ${textCondicionalConsumoMensal} que o planejado.`;
                        var mensagemConsumoAnual = `Sua média de consumo anual é de <b>${consumoMedioAnual.toFixed(2)} kWh</b>, representando <b>${Math.abs(porcentagemConsumoMedioAnual.toFixed(2))}%</b> a ${textCondicionalConsumoAnual} que o planejado.`;

                        var elementoConsumoMensal = $('<li>').addClass(`list-group-item ${classeBgConsumoMensal} ${textColorConsumoMensal}`).html(`<i class="feather ${classeIconConsumoMensal} me-3 ${textColorConsumoMensal}"></i> ${mensagemConsumoMensal}`);
                        var elementoConsumoAnual = $('<li>').addClass(`list-group-item ${classeBgConsumoAnual} ${textColorConsumoAnual}`).html(`<i class="feather ${classeIconConsumoAnual} me-3 ${textColorConsumoAnual}"></i> ${mensagemConsumoAnual}`);

                        // Limpar a ul antes de recriar as li
                        elementoContainer.empty();

                        // Adicione as novas li diretamente à ul
                        elementoContainer.append(
                            $('<li>').addClass(`list-group-item ${classeBgConsumoOriginal} text-black`).html(`<i class="feather icon-file-text me-3 text-black"></i> ${mensagemConsumoOriginal}`),
                            elementoConsumoMensal,
                            elementoConsumoAnual
                        );

                        // Habilitar todas as abas
                        $('#myTab .nav-link').removeClass('disabled');
                        
                        // Desabilita a última aba caso esteja com inconsistência no consumo inicial do projeto
                        if (consumoInicialProjeto === 0) {
                            $('#analise-tab').addClass('disabled');
                        }

                        // Remover o texto "Dados não encontrados" da primeira aba
                        $('#consumo p.text-center').remove();

                        $('#consumo').html(criarSwitch());
                        
                        if (Object.keys(data).length > 1) {
                            // Obtenha o texto do primeiro item do dropdown "consumo-dropdown"
                            var textoDropdown = $('#consumo-dropdown .dropdown-menu li:last-child').text();
                            // Defina o texto no elemento com ID "consumo-texto-dinamico"
                            $('#consumo-texto-dinamico').text(textoDropdown);
                        } else {
                            var codigo = Object.keys(data)[0];
                            $('#consumo-texto-dinamico').text(codigo);
                            $('#injecao-texto-dinamico').text(codigo);
                            $('#faturado-texto-dinamico').text(codigo);
                        }

                        $('#consumo').append(criarProgressBars());

                        // Receber a resposta do endpoint do Django aqui
                        log("Resposta do Django:", data);
                        
                        for (var codigo in data) {
                            // Acessar a chave (código da instalação)
                            log("Código da instalação:", codigo);

                            // Acessar os dados da instalação
                            var instalacao = data[codigo];
                            log("Dados da instalação:", instalacao);
                            
                            $.each(instalacao, function(index, item) {
                                // Atualize o progress-label-month
                                $('.progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);

                                // Atualize a progress-bar
                                $('.progress-container:eq(' + index + ') .progress-bar')
                                    .css('width', item.percent + '%')
                                    .attr('aria-valuenow', item.percent);

                                // Atualize o progress-label
                                $('.progress-container:eq(' + index + ') .progress-label').text(item.consumo + ' kWh');
                                $('.progress-bar').addClass('progress-bar-animated');
                            });

                            $.each(instalacao, function(index, item) {
                                // Atualize o progress-label-month
                                $('#injecao .progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);

                                // Atualize a progress-bar
                                $('#injecao .progress-container:eq(' + index + ') .progress-bar')
                                    .css('width', item.percent_inject + '%')
                                    .attr('aria-valuenow', item.percent_inject);

                                // Atualize o progress-label
                                $('#injecao .progress-container:eq(' + index + ') .progress-label').text(item.energia_injetada_fora_ponta + ' kWh');
                                $('.progress-bar').addClass('progress-bar-animated');
                            });

                            $.each(instalacao, function(index, item) {
                                // Atualize o progress-label-month
                                $('#faturado .progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);

                                // Atualize a progress-bar
                                $('#faturado .progress-container:eq(' + index + ') .progress-bar')
                                    .css('width', item.percent_valor + '%')
                                    .attr('aria-valuenow', item.percent_valor);

                                // Atualize o valor
                                $('#faturado .progress-container:eq(' + index + ') .valor').text('R$ ' + item.valor);

                                // Atualize a energia faturada fora de ponta
                                $('#faturado .progress-container:eq(' + index + ') .energia').text((item.energia_faturada_fora_ponta > 0 ? Math.round(item.energia_faturada_fora_ponta) : 0) + ' kWh');
                                $('.progress-bar').addClass('progress-bar-animated');
                            });
                        }
                        
                        var economiaTotal = 0;
                        for (var mesAno in info['economia']) {
                            log('mesAno ' + mesAno, 'mesAnoAtual ' + mesAnoAtual, 'economia ' + info['economia'][mesAno]);
                            if (mesAno === mesAnoAtual)
                                economiaTotal = parseFloat(info['economia'][mesAno]);  // Adiciona a economia desta instalação à soma total
                        }
                        var economiaText = `Esse mês você economizou R$ ${economiaTotal.toFixed(2)} com sua geração de energia.`;
                        
                        // Atualiza o texto e reinclui o ícone
                        $('#analise-economia').html(`<i class="feather icon-trending-down me-3"></i> ${economiaText}`);

                    }
                    
                    // Adicione um evento de clique ao switch
                    $('#flexSwitchCheckDefault').on('click', function() {
                        
                        $('#consumo .legenda').remove();
                        
                        // Armazene o valor do item selecionado
	                    var selectedItem = $('#consumo-texto-dinamico').text();
                        
                        // Verifique se o switch está ativado
                        if ($(this).is(':checked')) {
                            
                            // Limpe o conteúdo do elemento #consumo
                            $('#consumo').children().not('.form-check').not('.mb-4').not('#consumo-texto-dinamico').not('.mobile-only').remove();
                            
                            // Recrie os elementos removidos da primeira aba
                            var progressContainers = '';
                            for (var i = 0; i < 13; i++) {
                                progressContainers += `
                                    <div class="progress-container">
                                        <p class="progress-label-month"></p>
                                        <div class="progress m-t-5">
                                            <div class="progress-bar progress-bar-striped bg-danger" role="progressbar"
                                                style="width: 0%;" aria-valuenow="0" aria-valuemin="0"
                                                aria-valuemax="100">
                                                <span class="progress-label"></span>
                                            </div>
                                            <div class="progress-bar progress-bar-striped bg-success" role="progressbar"
                                                style="width: 0%;" aria-valuenow="0" aria-valuemin="0"
                                                aria-valuemax="100">
                                                <span class="progress-label"></span>
                                            </div>
                                        </div>
                                        <p class="progress-label total"></p>
                                    </div>`;
                            }
                            $('#consumo').append(progressContainers);
                            $('.progress-bar').addClass('progress-bar-animated');

                            for (var codigo in data) {
                                var instalacao = data[codigo];
                                
                                // Verifique se este é o item selecionado
                                if (codigo === selectedItem) {
                                    
                                    // Remova a mensagem existente
		                            $('#consumo .mobile-only').remove();
                                    
                                    var erroDetectado = false;
                                    var ultimoContainer;

                                    $.each(instalacao, function(index, item) {  
                                        var container = $('.progress-container:eq(' + index + ')');
                                        ultimoContainer = container;

                                        container.find('.progress-label-month').text(item.mes_ano);

                                        // Verifique se há um problema e se o mês atual está na lista info_adicional e se não é o primeiro item
                                        if (info['problema'] && info['key_error'] === 'autoconsumo_incompleto' && info['info_adicional'].includes(item.mes_ano) && index !== 0) {
                                            // Crie uma única barra de progresso cinza que vai até 100%
                                            var progressBar = container.find('.progress-bar').eq(0);
                                            progressBar.css('width', '100%')  // Ajuste para 100%
                                                .attr('aria-valuenow', 100)  // Ajuste para 100%
                                                .css('background-color', 'rgba(128, 128, 128, 0.7)')  // Adicione a cor cinza com 70% de opacidade
                                                .removeClass('bg-danger')  // Remova a classe bg-danger
                                                .css('position', 'relative');  // Adicione position: relative

                                            // Coloque o símbolo ⚠️ no meio da barra
                                            progressBar.html('<span class="lightning-symbol" style="position: absolute; width: 100%; text-align: center;">⚠️</span>');

                                            container.find('.progress-label.total').text('* XX kWh');
                                            // Adicione tooltip ao container
                                            container.attr('data-toggle', 'tooltip')
                                                .attr('title', 'Consumo: ' + Math.trunc(item.consumo) + ' kWh, Autoconsumo: ⚠️')
                                                .tooltip();
                                            erroDetectado = true;
                                        }
                                        else {
                                            
                                            var progressBar1 = container.find('.progress-bar').eq(0);
                                            progressBar1.css('width', item.percent_ct_consumo + '%')
                                                .attr('aria-valuenow', item.percent_ct_consumo);
                                            progressBar1.find('.progress-label').text(Math.trunc(item.consumo)).addClass('progress-bar-label');

                                            var progressBar2 = container.find('.progress-bar').eq(1);
                                            var geracaoTotal = item.soma_geracao - item.energia_injetada_fora_ponta;
                                            var geracaoTotalFormatado = geracaoTotal.toFixed(2); // Formata para duas casas decimais
                                            progressBar2.addClass('overflow-visible');
                                            progressBar2.addClass('green-bar');
                                            progressBar2.css('width', item.percent_ct_geracao + '%')
                                                .attr('aria-valuenow', item.percent_ct_geracao);
                                            
                                            if (geracaoTotalFormatado != 0) {
                                                progressBar2.find('.progress-label').text(Math.trunc(geracaoTotalFormatado)).addClass('progress-bar-label');
                                            }

                                            var consumoTotalFormatado = item.consumo_total.toFixed(2); // Formata para duas casas decimais
                                            container.find('.progress-label.total').text(consumoTotalFormatado + ' kWh');
                                            // Adicione tooltip ao container
                                            container.attr('data-toggle', 'tooltip')
                                                .attr('title', 'Consumo: ' + Math.trunc(item.consumo) + ' kWh, Autoconsumo: ' + geracaoTotalFormatado + ' kWh')
                                                .tooltip();
                                        }

                                        $('.progress-bar').addClass('progress-bar-animated');
                                        
                                        if (index === instalacao.length - 1) {
                                            if (erroDetectado) {
                                            // Adicione a mensagem no final do último progress bar
                                            container.after('<p class="mobile-only">Você pode clicar no gráfico para verificar os valores</p>');
                                            } else {
                                            container.after('<br><p class="mobile-only">Você pode clicar no gráfico para verificar os valores</p>');
                                            }
                                        }
                                    });
                                    
                                    if (erroDetectado) {
                                        // Adicione a legenda explicando o símbolo de exclamação no final do último progress bar
                                        ultimoContainer.after('<br><p class="legenda">⚠️ - Por falta de dados de geração, não é possível calcular o autoconsumo nos meses que apresentam esse símbolo.</p>');
                                    }
                                    
                                    if ($('#flexSwitchCheckDefault').is(':checked')) {
                                        $('.mobile-only').show();
                                        if (erroDetectado) {
                                            $('.legenda').show();
                                        }
                                    } else {
                                        $('.mobile-only').hide();
                                        if (erroDetectado) {
                                            $('.legenda').hide();
                                        }
                                    }
                                }
                            }
                            
                        } else {
                            
                            // Limpe o conteúdo do elemento #consumo
                            $('#consumo').children().not('.form-check').not('.mb-4').not('#consumo-texto-dinamico').not('.legenda').remove();
                            
                            $('#consumo').append(criarProgressBars());

                            // Receber a resposta do endpoint do Django aqui
                            log("Resposta do Django:", data);

                            for (var codigo in data) {
                                
                                // Verifique se este é o item selecionado
		                        if (codigo === selectedItem) {
                                    // Acessar a chave (código da instalação)
                                    log("Código da instalação:", codigo);

                                    // Acessar os dados da instalação
                                    var instalacao = data[codigo];
                                    log("Dados da instalação:", instalacao);
                                                
                                    $.each(instalacao, function(index, item) {
                                        // Atualize o progress-label-month
                                        $('.progress-container:eq(' + index + ') .progress-label-month').text(item.mes_ano);

                                        // Atualize a progress-bar
                                        $('.progress-container:eq(' + index + ') .progress-bar')
                                            .css('width', item.percent + '%')
                                            .attr('aria-valuenow', item.percent);

                                        // Atualize o progress-label
                                        $('.progress-container:eq(' + index + ') .progress-label').text(item.consumo + ' kWh');
                                        $('.progress-bar').addClass('progress-bar-animated');
                                    }); 
                                }
                            }
                        }                        
                    });
                    $('.progress-bar').addClass('progress-bar-animated');
                    
                    $('a[data-toggle="tab"]').not('#consumo-tab').on('click', function () {
                        if ($('#flexSwitchCheckDefault').is(':checked')) {
                            $('#flexSwitchCheckDefault').click(); // Desmarcar o switch
                        }
                    });
                    $('.dropdown-menu').on('click', 'a', function () {
                        if ($('#flexSwitchCheckDefault').is(':checked')) {
                            $('#flexSwitchCheckDefault').click(); // Desmarcar o switch
                        }
                    });
                    ///////////////////////////////// SESSÃO DE PREVISÕES ///////////////////////////////
                    if (previsao) {
                        var mesesAnalisados = previsao.meses_analisados;
                        var percentagemDifMedia = previsao.percentagem_dif_medias;
                        var percentagemMediaAnual = previsao.percentagem_media_anual;
                        var iconDifMedia = 'icon-check-circle';
                        var colorDifMedia;
                        var textDifMedia;
                        var aumentaDiminui = 'aumenta';
                        
                        
                        if (percentagemDifMedia <= 0) {
                            colorDifMedia = 'bg-success';
                            textDifMedia = 'reduzindo';
                            aumentaDiminui = 'diminui';
                        } else if (percentagemDifMedia <= 15) {
                            colorDifMedia = 'bg-warning';
                            textDifMedia = 'aumentando';
                        } else {
                            colorDifMedia = 'bg-danger';
                            textDifMedia = 'aumentando';
                        }
                        
                            
                        // Atualiza o texto e reinclui o ícone
                        // Mês referência para análise: <b>' + mesAnoAtual + '</b>';
                        $('#percent_dif').html(`
                            <ul class="list-group mb-3">
                                <li class="list-group-item bg-light text-black">
                                    <i class="feather icon-calendar me-3 text-black"></i>
                                        Meses disponíveis para análise: <b>${mesesAnalisados}</b>
                                </li>
                            </ul>
                            <ul class="list-group">
                                <li class="list-group-item ${colorDifMedia} text-white">
                                    <i class="feather ${iconDifMedia} me-3"></i> 
                                    Seu consumo está ${textDifMedia} a uma taxa média de ${percentagemDifMedia}% ao mês.
                                </li>
                                <li class="list-group-item ${colorDifMedia} text-white">
                                    <i class="feather ${iconDifMedia} me-3"></i> 
                                    Isso representa uma média de ${percentagemMediaAnual}% ao ano.
                                </li>
                            </ul>
                        `);
                            
                        ////////////////////////////// MONTAGEM DO GRÁFICO DE PREVISÃO ///////////////////
                            
                        $(document).ready(function() {
                            // Primeiro, vamos preencher o dropdown com as instalações
                            for (var codigo in data) {
                                $('#instalacao-dropdown').append('<option value="' + codigo + '">' + codigo + '</option>');
                            }

                            // Em seguida, vamos criar um evento de mudança para o dropdown
                            $('#instalacao-dropdown').change(function() {
                                var codigo = $(this).val(); // Obtemos o código da instalação selecionada

                                // Removemos o gráfico antigo, se houver
                                $('#chart-container-preview').empty();

                                var instalacao = data[codigo];
                                var instalacao_key = codigo;

                                // Criamos um novo elemento div para o gráfico
                                var idDoGrafico = 'grafico-' + codigo;
                                $('#chart-container-preview').append('<canvas id="' + idDoGrafico + '"></canvas>');

                                // Primeiro, vamos criar um array vazio para armazenar nossos dados formatados
                                var dadosFormatados = [];

                                // Vamos pegar apenas os 12 primeiros registros de cada instalação
                                var registros = instalacao.slice(0, 12);

                                $.each(registros, function(index, item) {
                                    // Vamos criar um novo objeto de dados para cada item
                                    var mesAno = item.mes_ano.split("/");
                                    var ano = parseInt(mesAno[1]) + 1;
                                    var mesAnoAtualizado = mesAno[0] + "/" + ano;

                                    var dadosDoMes = {
                                        mes: mesAnoAtualizado, // usamos o valor de mes_ano como o rótulo do eixo x
                                        consumo_total: item.consumo_total, // usamos o valor de consumo_total para a primeira barra
                                        consumo_total_mais_percentagemDifMedia: item.consumo_total + ((item.consumo_total * percentagemDifMedia)/100) // usamos a soma de consumo_total e percentagemDifMedia para a segunda barra
                                    };

                                    // Adicionamos o objeto de dados ao nosso array de dados formatados
                                    dadosFormatados.push(dadosDoMes);
                                });

                                // Reordenamos os dados por mês/ano em ordem crescente
                                dadosFormatados.sort(function(a, b) {
                                    return new Date(a.mes.split("/").reverse().join("-")) - new Date(b.mes.split("/").reverse().join("-"));
                                });

                                // Agora que temos nossos dados formatados, podemos criar o gráfico
                                var ctx = document.getElementById(idDoGrafico).getContext('2d');
                                graficos[codigo] = new Chart(ctx, {
                                    type: 'bar',
                                    data: {
                                        labels: dadosFormatados.map(function(item) { return item.mes; }),
                                        datasets: [{
                                            label: 'Consumo Total',
                                            data: dadosFormatados.map(function(item) { return item.consumo_total; }),
                                            backgroundColor: '#be2929'
                                        }, {
                                            label: 'Consumo Presumido',
                                            data: dadosFormatados.map(function(item) { return Math.ceil(item.consumo_total_mais_percentagemDifMedia); }),
                                            backgroundColor: '#7A92A3'
                                        }]
                                    },
                                    options: {
                                        responsive: true,
                                        maintainAspectRatio: false,
                                        plugins: {
                                            legend: {
                                                labels: {
                                                    color: 'black'
                                                }
                                            },
                                            tooltip: {
                                                enabled: true,
                                                intersect: true, // Altere para true
                                                mode: 'nearest',
                                                callbacks: {
                                                    label: function(context) {
                                                        var label = context.dataset.label || '';
                                                        if (label) {
                                                            label += ': ';
                                                        }
                                                        if (context.parsed.y !== undefined) {
                                                            label += context.parsed.y;
                                                        }
                                                        label += ' kWh';
                                                        return label;
                                                    }
                                                }
                                            }
                                        },
                                        scales: {
                                            x: {
                                                ticks: {
                                                    color: 'black',
                                                },
                                                display: true,
                                                scaleLabel: {
                                                    display: true,
                                                    labelString: 'Mês'
                                                }
                                            },
                                            y: {
                                                display: true,
                                                scaleLabel: {
                                                    display: true,
                                                    labelString: 'Consumo'
                                                },
                                                ticks: {
                                                    color: 'black',
                                                    // Inclui 'kWh' no final dos rótulos do eixo y
                                                    callback: function(value, index, values) {
                                                        return value + ' kWh';
                                                    }
                                                }
                                            }
                                        }
                                    }
                                });

                                var canvas = document.getElementById(idDoGrafico);
                                if (screenSize <= 400){
                                    log('screensize < 400 ' + screenSize);
                                    canvas.style.height='300px'; // Ajuste este valor conforme necessário
                                } else {
                                    log('screensize > 400 ' + screenSize);
                                    canvas.style.height='400px'; // Ajuste este valor conforme necessário
                                }
                                var ctx = canvas.getContext('2d');

                            });

                            // Disparamos o evento de mudança manualmente para exibir o gráfico da primeira instalação
                            $('#instalacao-dropdown').change();
                            for (var codigo in graficos) {
                                if (graficos.hasOwnProperty(codigo)) {
                                    updateChartColor(graficos[codigo], theme);
                                }
                            }
                        });
                    } else {
                        var cardBlockPreview = $('.card-block-preview');
                        cardBlockPreview.empty();
                        cardBlockPreview.append('<p class="text-center mt-3 mb-4">Dados não encontrados</p>');
                    }

                },
                error: function(error) {
                    console.error("Erro na requisição AJAX:", error);
                }
            });
            
        }
        
        function criarSwitch() {
            var switchHtml = `
            <h5 class="mb-4">Consumo anual em kWh:</h5>
            <span id="consumo-texto-dinamico"></span>
            <div class="form-check form-switch mb-4">
                <input class="form-check-input" type="checkbox" role="switch" id="flexSwitchCheckDefault">
                <label class="form-check-label" for="flexSwitchCheckDefault">Incluir o consumo da energia gerada? (autoconsumo)</label>
                <i class="feather icon-help-circle" title="Autoconsumo é a energia gerada e consumida imediatamente, não sendo contabilizado pela concessionária. Aparecerá em verde no gráfico." style="font-size: 1em;"></i>
            </div>
            `;
            return switchHtml;
        }
        
        function criarProgressBars() {
            var progressContainers = '';
            for (var i = 0; i < 13; i++) {
                progressContainers += `
                <div class="progress-container">
                <p class="progress-label-month"></p>
                <div class="progress m-t-5">
                <div class="progress-bar progress-bar-striped bg-danger" role="progressbar"
                style="width: 0%;" aria-valuenow="0" aria-valuemin="0"
                aria-valuemax="100">
                </div>
                </div>
                <p class="progress-label"></p>
                </div>`;
            }
            return progressContainers;
        }

        function getCookie(name) {
            var value = "; " + document.cookie;
            var parts = value.split("; " + name + "=");
            if (parts.length === 2) return parts.pop().split(";").shift();
        }

        var screenSize = window.innerWidth;

        (function() {
        function updateButtonText() {
            var button = document.getElementById('custom-range-button');
            if (window.innerWidth <= 450) {
            button.textContent = 'Personaliz.';
            } else {
            button.textContent = 'Período Personalizado';
            }
        }

        // Chama a função ao carregar a página
        updateButtonText();

        // Chama a função ao redimensionar a tela
        window.addEventListener('resize', updateButtonText);
        })();
        
        function updateChartColor(chart, theme) {
            
            var cor;
            
            if (theme === 'dark') {
                cor = 'white';
            } else {
                cor = 'black';
            }
            
            // Atualizar a cor da legenda
            chart.options.plugins.legend.labels.color = cor;

            // Atualizar a cor dos rótulos do eixo X
            chart.options.scales.x.ticks.color = cor;

            // Atualizar a cor dos rótulos do eixo Y
            chart.options.scales.y.ticks.color = cor;

            // Aplicar as alterações
            chart.update();
        }


        function updateButtonTheme(theme) {

            var buttons = document.querySelectorAll('.btn-date');
            buttons.forEach(function(button) {
                if (theme === 'dark') {
                    button.classList.remove('btn-outline-secondary');
                    button.classList.add('btn-secondary');
                } else {
                    button.classList.remove('btn-secondary');
                    button.classList.add('btn-outline-secondary');
                }
            });
            for (var codigo in graficos) {
                if (graficos.hasOwnProperty(codigo)) {
                    updateChartColor(graficos[codigo], theme);
                }
            }
        };
        


        var theme = 'dark';
        var themeSwitch = document.getElementById('theme-switch');
        if (themeSwitch) {
            // Verifique o valor inicial do themeSwitch e dispare um evento de clique no botão apropriado
            theme = themeSwitch.checked ? 'light' : 'dark';
            updateButtonTheme(theme); // Função para atualizar o tema do botão
            if (theme === 'dark') {
                document.getElementById('dark-theme-button').click();
                var dropdownContainer = document.getElementById('month-year-container');  // Seleciona a div que engloba os dropdowns
                dropdownContainer.classList.add('dark-theme');  // Adiciona a classe 'dark-theme' à div
            } else {
                document.getElementById('light-theme-button').click();
                var dropdownContainer = document.getElementById('month-year-container');  // Seleciona a div que engloba os dropdowns
                dropdownContainer.classList.remove('dark-theme');  // Remove a classe 'dark-theme' da div
            }
            // Adicione o manipulador de eventos change ao themeSwitch
            themeSwitch.addEventListener('change', function() {
                theme = themeSwitch.checked ? 'light' : 'dark';
                updateButtonTheme(theme); // Função para atualizar o tema do botão
                // Dispare um evento de clique no botão apropriado
                if (theme === 'dark') {
                    document.getElementById('dark-theme-button').click();
                    var dropdownContainer = document.getElementById('month-year-container');  // Seleciona a div que engloba os dropdowns
                    dropdownContainer.classList.add('dark-theme');  // Adiciona a classe 'dark-theme' à div
                } else {
                    document.getElementById('light-theme-button').click();
                    var dropdownContainer = document.getElementById('month-year-container');  // Seleciona a div que engloba os dropdowns
                    dropdownContainer.classList.remove('dark-theme');  // Remove a classe 'dark-theme' da div
                }
            });
        }

        return screenSize;
    }
    """,
    Output('output-screen', 'children'),
    [Input('hidden-input', 'value')],
)


@app.callback(
    Output('selected-date-range', 'data'),  # Define a saída como os dados do intervalo de datas selecionado
    Input('apply-button', 'n_clicks'),  # Recebe o número de cliques no botão de aplicar
    State('date-range-picker', 'start_date'),  # Recebe a data de início do intervalo selecionado
    State('date-range-picker', 'end_date'),  # Recebe a data de término do intervalo selecionado
)
def update_selected_date_range(n_clicks, start_date, end_date):
    """
    Atualiza os dados do intervalo de datas selecionado quando o botão de aplicar é clicado.

    Parameters:
        n_clicks (int): O número de cliques no botão de aplicar.
        start_date (str): A data de início do intervalo selecionado.
        end_date (str): A data de término do intervalo selecionado.

    Returns:
        (dict): Um dicionário contendo as datas de início e término do intervalo selecionado.
    """
    # Verifica se o botão de aplicar foi clicado
    if n_clicks:
        # Retorna os dados do intervalo de datas
        return {'start_date': start_date, 'end_date': end_date}
    
    # Caso contrário, mantém os dados inalterados
    return dash.no_update


@app.callback(
    Output('custom-range-container', 'style'),  # Define a saída como o estilo do contêiner de intervalo personalizado
    Output('date-range-picker', 'start_date'),  # Define a saída como a data de início do seletor de datas
    Output('date-range-picker', 'end_date'),  # Define a saída como a data de término do seletor de datas
    Input('custom-range-button', 'n_clicks'),  # Recebe o número de cliques no botão de intervalo personalizado
    Input('apply-button', 'n_clicks'),  # Recebe o número de cliques no botão de aplicar
    Input('cancel-button', 'n_clicks'),  # Recebe o número de cliques no botão de cancelar
    State('custom-range-container', 'style'),  # Recebe o estilo atual do contêiner de intervalo personalizado
    State('date-range-picker', 'start_date'),  # Recebe a data de início atual do seletor de datas
    State('date-range-picker', 'end_date'),  # Recebe a data de término atual do seletor de datas
)
def toggle_custom_range_container(
    custom_range_clicks,
    apply_clicks,
    cancel_clicks,
    container_style,
    start_date,
    end_date,
):
    """
    Alterna a exibição do contêiner de intervalo personalizado e atualiza as datas do seletor de datas.

    Parameters:
        custom_range_clicks (int): O número de cliques no botão de intervalo personalizado.
        apply_clicks (int): O número de cliques no botão de aplicar.
        cancel_clicks (int): O número de cliques no botão de cancelar.
        container_style (dict): O estilo atual do contêiner de intervalo personalizado.
        start_date (str): A data de início atual do seletor de datas.
        end_date (str): A data de término atual do seletor de datas.

    Returns:
        container_style (dict): Estilo atualizado do contêiner.
        start_date (str): Data inicial do seletor.
        end_date (str): Data final do seletor.
    """
    ctx = dash.callback_context  # Obtém o contexto da chamada de retorno

    # Verifica se a chamada de retorno foi acionada
    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]  # Obtém o ID do botão acionado

        # Lógica para o botão de intervalo personalizado
        if button_id == 'custom-range-button':
            # Alterna entre exibir e ocultar o contêiner de intervalo personalizado
            container_style['display'] = 'block' if 'none' in container_style['display'] else 'none'
        # Lógica para o botão de aplicar
        elif button_id == 'apply-button':
            # Oculta o contêiner de intervalo personalizado
            container_style['display'] = 'none'
        # Lógica para o botão de cancelar
        elif button_id == 'cancel-button':
            # Oculta o contêiner de intervalo personalizado e redefine as datas para None
            container_style['display'] = 'none'
            start_date = None
            end_date = None

    # Retorna a tupla contendo o estilo atualizado do contêiner e as datas atualizadas do seletor
    return container_style, start_date, end_date


@app.callback(
    Output('day-selector', 'options'),  # Define a saída como as opções do seletor de dia
    [Input('month-selector', 'value'), Input('year-selector', 'value')],  # Recebe os valores selecionados do seletor de mês e ano
)
def update_day_selector(selected_month, selected_year):
    """
    Atualiza as opções do seletor de dia com base no mês e ano selecionados.

    Parameters:
        selected_month (int): O mês selecionado.
        selected_year (int): O ano selecionado.

    Returns:
        List[dict]: Uma lista de dicionários contendo as opções do seletor de dia.
    """
    if selected_month and selected_year:  # Verifica se o mês e o ano estão selecionados
        num_days = calendar.monthrange(selected_year, selected_month)[1]  # Obtém o número de dias no mês
        return [{'label': str(i), 'value': i} for i in range(1, num_days + 1)]  # Gera as opções do seletor de dia
    else:
        return []  # Retorna uma lista vazia se o mês ou ano não estiverem selecionados


@app.callback(
    Output('energy-generation-graph', 'figure'),
    [
        Input('client-selector', 'value'),
        Input('total-button', 'n_clicks_timestamp'),
        Input('year-button', 'n_clicks_timestamp'),
        Input('month-button', 'n_clicks_timestamp'),
        Input('day-button', 'n_clicks_timestamp'),
        Input('day-selector', 'value'),
        Input('month-selector', 'value'),
        Input('year-selector', 'value'),
        Input(
            'theme-store', 'data'
        ),  # Ouça mudanças na propriedade data/value do componente intermediário
        Input('output-screen', 'children'),
        Input('store_resize', 'data'),
        Input(
            'date-range-picker', 'start_date'
        ),  # Adicione o id do DatePickerRange como um Input
        Input(
            'date-range-picker', 'end_date'
        ),  # Adicione o id do DatePickerRange como um Input
        Input('user-type-store', 'data'),  # Use o Store como entrada
    ],
)
def update_graph(
    selected_clients,
    total_clicks,
    year_clicks,
    month_clicks,
    day_clicks,
    selected_day,
    selected_month,
    selected_year,
    theme_data,
    screen_size,
    screen_resize,
    date_picker_start_date,
    date_picker_end_date,
    user_type_store_data,
):
    """
    Atualiza o gráfico de geração de energia com base nos parâmetros e opções selecionados.

    Parameters:
        selected_clients (list): Lista de IDs de clientes selecionados.
        total_clicks (int): Carimbo de data/hora do último clique no botão "Total".
        year_clicks (int): Carimbo de data/hora do último clique no botão "Ano".
        month_clicks (int): Carimbo de data/hora do último clique no botão "Mês".
        day_clicks (int): Carimbo de data/hora do último clique no botão "Dia".
        selected_day (int): Dia selecionado no seletor de dia.
        selected_month (int): Mês selecionado no seletor de mês.
        selected_year (int): Ano selecionado no seletor de ano.
        theme_data (dict): Dados do tema do aplicativo.
        screen_size (str): Tamanho da tela.
        screen_resize (int): Informações sobre o redimensionamento da tela.
        date_picker_start_date (str): Data de início selecionada no DatePickerRange.
        date_picker_end_date (str): Data de término selecionada no DatePickerRange.
        user_type_store_data (dict): Dados armazenados sobre o tipo de usuário.

    Returns:
        figure (dict): Um dicionário contendo a figura atualizada do gráfico de geração de energia.
    """
    # Determine o intervalo de tempo selecionado com base nos botões clicados
    selected_time_range = 'day'  # Valor padrão

    if (
        total_clicks
        and (not year_clicks or total_clicks > year_clicks)
        and (not month_clicks or total_clicks > month_clicks)
        and (not day_clicks or total_clicks > day_clicks)
    ):
        selected_time_range = 'total'
    elif (
        year_clicks
        and (not total_clicks or year_clicks > total_clicks)
        and (not month_clicks or year_clicks > month_clicks)
        and (not day_clicks or year_clicks > day_clicks)
    ):
        selected_time_range = 'year'
    elif (
        month_clicks
        and (not total_clicks or month_clicks > total_clicks)
        and (not year_clicks or month_clicks > year_clicks)
        and (not day_clicks or month_clicks > day_clicks)
    ):
        selected_time_range = 'month'
    elif (
        day_clicks
        and (not total_clicks or day_clicks > total_clicks)
        and (not year_clicks or day_clicks > year_clicks)
        and (not month_clicks or day_clicks > month_clicks)
    ):
        selected_time_range = 'day'

    # Recupere os dados de geração de energia dos clientes selecionados
    data = []

    # Crie uma lista vazia para armazenar os DataFrames
    data_frames = []

    # Crie um DataFrame vazio para armazenar todos os dados
    all_data = pd.DataFrame(columns=['Timestamp', 'Energystamp', 'Cliente'])

    st_date = ''
    ed_date = ''

    user_type = user_type_store_data['user_type']
    client_id = user_type_store_data['client_id']
    if client_id:
        # if user_type not in ['admin', 'integrador'] :
        selected_clients = [client_id]
    else:
        if not selected_clients:
            selected_clients = [Cliente.objects.first().id]

    if date_picker_start_date:
        date_picker_start_date = datetime.datetime.strptime(
            date_picker_start_date, '%Y-%m-%d'
        )
    if date_picker_end_date:
        date_picker_end_date = datetime.datetime.strptime(
            date_picker_end_date, '%Y-%m-%d'
        )

    # Envio para um endpoint o cliente selecionado
    # Gere a URL do endpoint usando a função reverse do Django
    # url_django_base = reverse('atualizar_tab')
    # url_cliente_csrf = reverse('csrf')

    # # Montar a URL completa usando o IP ou nome do servidor e a porta atual
    # django_server = "localhost"  # Substitua pelo IP ou nome do servidor
    # django_port = "8000"  # Substitua pela porta atual

    # client = requests.session()

    # url_django = urljoin(f'http://{django_server}:{django_port}', url_django_base)
    # url_csrf = urljoin(f'http://{django_server}:{django_port}', url_cliente_csrf)

    # response = client.get(url_csrf)
    # #print('response', response.json())
    # csrftoken = response.json()['csrfToken']

    # # Inclua o token CSRF na requisição POST
    # headers = {'X-CSRFToken': csrftoken}
    # response = client.post(url_django, headers=headers, data={'cliente': selected_clients})

    for client_id in selected_clients:
        cliente = Cliente.objects.get(id=client_id)
        plant_name = cliente.plant_name
        # print('client id', client_id)
        if selected_time_range == 'total':
            if date_picker_start_date and date_picker_end_date:
                # Filtre os dados com base nas datas de início e fim selecionadas pelo DatePickerRange
                geracao = Geracao.objects.filter(
                    cliente__id=client_id,
                    timestamp__gte=date_picker_start_date,
                    timestamp__lte=date_picker_end_date,
                )
                xaxis_title = 'Year'
            else:
                geracao = Geracao.objects.filter(
                    cliente__id=client_id,
                )
                xaxis_title = 'Year'
            timestamps = [entry.timestamp.year for entry in geracao]
        elif selected_time_range == 'year':
            if date_picker_start_date and date_picker_end_date:
                # Filtre os dados com base nas datas de início e fim selecionadas pelo DatePickerRange
                geracao = Geracao.objects.filter(
                    cliente__id=client_id,
                    timestamp__gte=date_picker_start_date,
                    timestamp__lte=date_picker_end_date,
                ).order_by('timestamp__month')
                xaxis_title = str(date_picker_start_date.year)
            else:
                geracao = Geracao.objects.filter(
                    cliente__id=client_id,
                    timestamp__year=selected_year,
                ).order_by('timestamp__month')
                xaxis_title = str(selected_year)
            timestamps = [
                entry.timestamp.strftime('%b %y') for entry in geracao
            ]
        elif selected_time_range == 'month':
            if date_picker_start_date and date_picker_end_date:
                # Filtre os dados com base nas datas de início e fim selecionadas pelo DatePickerRange
                current_date = date_picker_start_date
                all_geracao = []
                while current_date <= date_picker_end_date:
                    geracao = Geracao.objects.filter(
                        cliente__id=client_id,
                        timestamp__date=current_date.date(),  # Filtra apenas por data, ignorando a hora
                    )
                    all_geracao.extend(list(geracao))
                    current_date += timedelta(days=1)

                # Concatene os resultados em um único DataFrame
                geracao = all_geracao

                xaxis_title = f'{calendar.month_name[date_picker_start_date.month]} {date_picker_start_date.day}, {date_picker_start_date.year} - {calendar.month_name[date_picker_end_date.month]} {date_picker_end_date.day}, {date_picker_end_date.year}'
            else:
                geracao = Geracao.objects.filter(
                    cliente__id=client_id,
                    timestamp__year=selected_year,
                    timestamp__month=selected_month,
                )

                xaxis_title = (
                    f'{calendar.month_name[selected_month]} {selected_year}'
                )

            timestamps = [
                entry.timestamp.strftime('%d/%m/%y') for entry in geracao
            ]

        else:

            # Obtenha o fuso horário atualmente configurado no Django
            current_timezone = get_current_timezone()

            if date_picker_start_date and date_picker_end_date:

                st_date = make_aware(
                    date_picker_start_date, timezone=current_timezone
                )
                ed_date = make_aware(
                    date_picker_end_date, timezone=current_timezone
                )

                # Filtre os dados com base nas datas de início e fim selecionadas pelo DatePickerRange
                current_date = date_picker_start_date
                all_geracao = []
                while current_date <= date_picker_end_date:
                    current_end_date = current_date + timedelta(days=1)
                    geracao_dia = GeracaoDiaria.objects.filter(
                        cliente__id=client_id,
                        timestamp__gte=current_date,
                        timestamp__lt=current_end_date,
                    )
                    all_geracao.extend(list(geracao_dia))
                    current_date += timedelta(days=1)

                # Concatene os resultados em um único DataFrame
                geracao_dia = all_geracao
                xaxis_title = f'{date_picker_start_date.day} de {calendar.month_name[date_picker_start_date.month]}, {date_picker_start_date.year} - {date_picker_end_date.day} de {calendar.month_name[date_picker_end_date.month]}, {date_picker_end_date.year}'

            else:
                start_date = datetime.datetime(
                    selected_year, selected_month, selected_day, 0, 0, 0
                )
                # Converta o objeto selected_day em um objeto com informações de fuso horário
                start_date = make_aware(start_date, timezone=current_timezone)
                end_date = start_date + timedelta(days=1)
                st_date = start_date
                ed_date = end_date
                geracao_dia = GeracaoDiaria.objects.filter(
                    cliente__id=client_id,
                    timestamp__gte=start_date,
                    timestamp__lt=end_date,
                )
                xaxis_title = f'{start_date.day} de {calendar.month_name[start_date.month]}, {start_date.year}'

            if cliente.inverter.name not in [
                'abb_fimer',
                'sungrow',
                'ecosolys',
            ]:
                # Ajuste a data de fim para ser o último horário do dia desejado
                ed_date = pd.to_datetime(ed_date) - pd.Timedelta(minutes=5)
                # Gere os timestamps
                timestamps = pd.date_range(
                    start=st_date, end=ed_date, freq='5min'
                )
            else:
                # Ajuste a data de fim para ser o último horário do dia desejado
                ed_date = pd.to_datetime(ed_date) - pd.Timedelta(minutes=15)
                # Gere os timestamps
                timestamps = pd.date_range(
                    start=st_date, end=ed_date, freq='15min'
                )

            # Converta os timestamps para o fuso horário desejado
            timestamps = timestamps.tz_convert('America/Sao_Paulo')
            # Converta os timestamps em strings
            timestamps = timestamps.strftime('%d/%m/%y %H:%M:%S').tolist()

            data = {}
            for entry in geracao_dia:
                # Converta o objeto de data e hora com informações de fuso horário para o fuso horário desejado
                timestamp = entry.timestamp.astimezone(
                    pytz.timezone('America/Sao_Paulo')
                )
                # Converta o objeto de data e hora com informações de fuso horário em uma string
                timestamp = timestamp.strftime('%d/%m/%y %H:%M:%S')
                data[timestamp] = entry.energystamp

            geracao = []
            for ts in timestamps:
                energia = data.get(ts, 0)
                geracao.append(
                    {
                        'Timestamp': ts,
                        'Energystamp': energia,
                        'Cliente': plant_name,
                    }
                )

        if selected_time_range == 'day':
            energystamps = [entry['Energystamp'] for entry in geracao]
        else:
            energystamps = [entry.energystamp / 1000 for entry in geracao]

        df = pd.DataFrame(
            {'Timestamp': timestamps, 'Energystamp': energystamps}
        )

        df = df.groupby('Timestamp', as_index=False).agg(
            {'Energystamp': 'sum'}
        )

        # Adicione uma coluna 'Cliente' ao DataFrame
        df['Cliente'] = plant_name

        # # Transformar valores zerados em NaN
        # df['Energystamp'] = df['Energystamp'].replace(0, np.nan)

        # Adicione o DataFrame à lista data_frames
        data_frames.append(df)

    # Concatene todos os DataFrames na lista data_frames
    all_data = pd.concat(data_frames)

    if selected_time_range == 'total':
        # Converta a coluna 'Timestamp' para o tipo de dados datetime
        all_data['Timestamp'] = pd.to_datetime(
            all_data['Timestamp'], format='%Y'
        )
    elif selected_time_range == 'year':
        # Converta a coluna 'Timestamp' para o tipo de dados datetime
        all_data['Timestamp'] = pd.to_datetime(
            all_data['Timestamp'], format='%b %y'
        )
    elif selected_time_range == 'month':
        # Converta a coluna 'Timestamp' para o tipo de dados datetime
        all_data['Timestamp'] = pd.to_datetime(
            all_data['Timestamp'], format='%d/%m/%y'
        )
    else:
        # Converta a coluna 'Timestamp' para o tipo de dados datetime
        all_data['Timestamp'] = pd.to_datetime(
            all_data['Timestamp'], format='%d/%m/%y %H:%M:%S'
        )

    # Ordene o DataFrame pela coluna 'Timestamp'
    all_data = all_data.sort_values(['Cliente', 'Timestamp'])

    # Ordenar os pontos dentro de cada cliente
    all_data = (
        all_data.groupby('Cliente')
        .apply(lambda x: x.sort_values('Timestamp'))
        .reset_index(drop=True)
    )

    # # Defina display.max_rows como None para mostrar todas as linhas
    # pd.set_option('display.max_rows', None)

    # # Imprima o DataFrame completo
    # print(all_data)

    # # Restaure o valor padrão de display.max_rows
    # pd.reset_option('display.max_rows')

    if selected_time_range == 'total':
        # Obtenha os anos com base nos valores da coluna 'Timestamp'
        all_data['Timestamp'] = all_data['Timestamp'].dt.year
    elif selected_time_range == 'year':
        # Obtenha os nomes abreviados dos meses com base nos valores da coluna 'Timestamp'
        all_data['Timestamp'] = all_data['Timestamp'].dt.strftime('%b %y')
    elif selected_time_range == 'month':
        if date_picker_start_date and date_picker_end_date:
            # Obtenha os dias com base nos valores da coluna 'Timestamp'
            all_data['Timestamp'] = all_data['Timestamp'].dt.strftime(
                '%d/%m/%y'
            )
        else:
            all_data['Timestamp'] = all_data['Timestamp'].dt.strftime('%d')
    else:
        if date_picker_start_date and date_picker_end_date:
            # Obtenha os horários com base nos valores da coluna 'Timestamp'
            all_data['Timestamp'] = all_data['Timestamp'].dt.strftime(
                '%d/%m/%y %H:%M'
            )
        else:
            all_data['Timestamp'] = all_data['Timestamp'].dt.strftime('%H:%M')

    # Carregue os templates
    template = ['bootstrap', 'superhero']
    load_figure_template(template)
    # print('theme', theme_data)
    theme = theme_data

    if theme == 'dark':
        template = 'superhero'
    else:
        template = 'bootstrap'

    width = 0

    if screen_resize and screen_resize != screen_size:
        width = float(screen_resize)
    else:
        width = float(screen_size)

    if selected_time_range == 'day':

        dias_diferenca = (ed_date + pd.DateOffset(minutes=5) - st_date).days
        if (
            date_picker_start_date
            and date_picker_end_date
            and (dias_diferenca < 5)
        ):

            all_data = all_data.reset_index(drop=True)
            # Substituir valores zero por NaN apenas nos pontos em que não há energia
            all_data.loc[all_data['Energystamp'] == 0, 'Energystamp'] = np.nan

            # Adicione uma coluna com o dia para cada linha
            all_data['Dia'] = pd.to_datetime(
                all_data['Timestamp'], format='%d/%m/%y %H:%M'
            ).dt.date

            all_data['Hora'] = all_data['Timestamp'].str.slice(start=-5)

            # Encontre o primeiro e o último índice não nulo para cada cliente e dia
            first_valid = all_data.groupby(['Cliente', 'Dia'])[
                'Energystamp'
            ].transform(lambda x: x.notnull().idxmax())
            last_valid = all_data.groupby(['Cliente', 'Dia'])[
                'Energystamp'
            ].transform(
                lambda x: x.size - x.iloc[::-1].notnull().values.argmax() - 1
            )

            # Preencha os valores NaN antes do primeiro índice não nulo e depois do último índice não nulo com 0
            all_data['Energystamp'] = all_data.apply(
                lambda x: 0
                if (
                    np.isnan(x['Energystamp'])
                    and (
                        x.name < first_valid.loc[x.name]
                        or x.name > last_valid.loc[x.name]
                    )
                )
                else x['Energystamp'],
                axis=1,
            )

        if dias_diferenca > 4:
            if width < 886:
                font_size = 20
            else:
                font_size = 30
            fig = go.Figure()
            fig.update_layout(
                xaxis=dict(
                    showgrid=False, zeroline=False, showticklabels=False
                ),
                yaxis=dict(
                    showgrid=False, zeroline=False, showticklabels=False
                ),
                template=template,
                annotations=[
                    dict(
                        x=0.5,
                        y=0.5,
                        xref='paper',
                        yref='paper',
                        text='Limite máximo de 4 dias',
                        showarrow=False,
                        font=dict(
                            size=font_size, color='rgba(128, 128, 128, 0.5)'
                        ),
                        align='center',
                        valign='middle',
                    )
                ],
            )
            # TODO: Os dticks precisam de mais ajuste fino
        else:

            def remove_zero_between_values(df):
                # Percorre o DataFrame
                for i in range(1, len(df) - 1):
                    # Verifica se o valor atual é 0.0 e se os valores anterior e próximo são diferentes de 0.0
                    if (
                        df['Energystamp'].iloc[i] == 0.0
                        and df['Energystamp'].iloc[i - 1] != 0.0
                        and df['Energystamp'].iloc[i + 1] != 0.0
                    ):
                        # Se sim, substitui o valor por NaN
                        df.loc[i, 'Energystamp'] = np.nan

                return df

            all_data = remove_zero_between_values(all_data)

            # Encontra todos os timestamps únicos em todo o conjunto de dados
            timestamps_unicos = pd.DataFrame(
                all_data['Timestamp'].unique(), columns=['Timestamp']
            )

            # Inicializa um novo DataFrame vazio para armazenar os dados reindexados
            all_data_reindexado = pd.DataFrame()

            # Para cada cliente, cria um novo DataFrame que contém todos os timestamps únicos
            for cliente in all_data['Cliente'].unique():
                # Filtra os dados para o cliente atual
                dados_cliente = all_data[all_data['Cliente'] == cliente]

                # Cria um novo DataFrame que contém todos os timestamps únicos
                dados_cliente_reindexado = timestamps_unicos.copy()

                # Adiciona uma coluna para 'Cliente'
                dados_cliente_reindexado['Cliente'] = cliente

                # Combina o novo DataFrame com os dados originais do cliente
                dados_cliente_reindexado = pd.merge(
                    dados_cliente_reindexado,
                    dados_cliente,
                    on=['Timestamp', 'Cliente'],
                    how='outer',
                )

                # Adiciona os dados reindexados do cliente ao DataFrame reindexado
                all_data_reindexado = pd.concat(
                    [all_data_reindexado, dados_cliente_reindexado]
                )

            # Agora, 'all_data_reindexado' é um DataFrame que contém todos os timestamps únicos para cada cliente,
            # e os valores de 'Energystamp' para os timestamps que não existiam originalmente para um cliente são preenchidos com NaN.

            all_data = all_data_reindexado

            # Ordena o DataFrame por 'Cliente' e 'Timestamp'
            all_data.sort_values(by=['Cliente', 'Timestamp'], inplace=True)

            # Redefine o índice do DataFrame
            all_data.reset_index(drop=True, inplace=True)

            # # Defina display.max_rows como None para mostrar todas as linhas
            # pd.set_option('display.max_rows', None)

            # # Imprima o DataFrame completo
            # printl(all_data)

            # # Restaure o valor padrão de display.max_rows
            # pd.reset_option('display.max_rows')
            # printl('>>>>>>>>>>> DATAFRAME', all_data)
            # Aplicar a interpolação cúbica apenas aos valores não nulos
            all_data['Energystamp'] = all_data.groupby('Cliente')[
                'Energystamp'
            ].transform(
                lambda x: x.interpolate(
                    method='pchip', limit_direction='both', limit_area='inside'
                )
            )

            fig = px.line(
                all_data,
                x='Timestamp',
                y='Energystamp',
                color='Cliente',
                template=template,
                hover_data={
                    'Cliente': True,
                    'Energystamp': ':.2f',
                    'Timestamp': False,  # se você não quiser mostrar o Timestamp
                },
                labels={'Cliente': 'Cliente', 'Energystamp': 'Geração'},
            )

            fig.update_yaxes(title='Geração de Energia (Wh)')

            if width < 886:
                dtick = 20 * dias_diferenca
                fig.update_layout(
                    xaxis=dict(
                        dtick=dtick,
                    )
                )
            else:
                dtick = 5 * dias_diferenca
                fig.update_layout(
                    xaxis=dict(
                        dtick=dtick,
                    )
                )

            if date_picker_start_date and date_picker_end_date:
                if theme == 'dark':
                    color = 'rgba(255, 255, 255, 0.3)'
                    font = dict(color='rgba(255,255,255,0.5)', size=12)
                else:
                    color = 'rgba(0, 0, 0, 0.8)'
                    font = dict(color='rgba(0,0,0,0.8)', size=12)

                # Adiciona as linhas em forma de tracejado e os textos dos dias
                for i in range(len(all_data) - 1):
                    current_date = all_data.loc[i, 'Dia']
                    next_date = all_data.loc[i + 1, 'Dia']
                    if current_date != next_date:
                        fig.add_shape(
                            type='line',
                            x0=all_data.loc[i, 'Timestamp'],
                            y0=min(all_data['Energystamp']),
                            x1=all_data.loc[i, 'Timestamp'],
                            y1=max(all_data['Energystamp']),
                            line=dict(
                                color=color,  # Definindo a cor com opacidade
                                width=1,
                                dash='dot',  # Definindo o estilo tracejado da linha
                            ),
                        )
                        fig.add_annotation(
                            x=all_data.loc[i, 'Timestamp'],
                            y=min(all_data['Energystamp'])
                            - 0.03
                            * (
                                max(all_data['Energystamp'])
                                - min(all_data['Energystamp'])
                            ),
                            text=next_date.strftime('%d/%m/%y'),
                            showarrow=False,
                            font=font,
                        )

                fig.update_xaxes(
                    tickmode='array',
                    tickvals=all_data.index[::dtick],
                    ticktext=all_data['Hora'][::dtick],
                )
        # fig.update_traces(
        #     hovertemplate='Cliente: %{meta}<br>Geração: %{y}<extra></extra>',
        #     meta=all_data['Cliente'],
        # )

    else:
        fig = px.bar(
            all_data,
            x='Timestamp',
            y='Energystamp',
            color='Cliente',
            barmode='group',
            template=template,
            hover_data={
                'Cliente': True,
                'Energystamp': ':.2f',
                'Timestamp': False,  # se você não quiser mostrar o Timestamp
            },
            labels={'Cliente': 'Cliente', 'Energystamp': 'Geração'},
        )

        fig.update_yaxes(title='Geração de Energia (kWh)')
        # Define o hovertemplate para cada traço
        # fig.update_traces(
        #     hovertemplate='Cliente: %{meta}<br>Geração: %{y}<extra></extra>',
        #     meta=all_data['Cliente'],
        # )

        if (
            date_picker_start_date
            and date_picker_end_date
            and (selected_time_range != 'year')
        ):
            if width > 886:
                tick = 7
            else:
                tick = 18
            fig.update_layout(xaxis=dict(dtick=tick))
        else:
            if width < 886:
                tick = 5
            else:
                tick = 1
            fig.update_layout(xaxis=dict(dtick=tick))

    fig.update_xaxes(title=xaxis_title)

    fig.update_layout(
        margin=dict(l=20, r=40, b=20),
        legend=dict(x=0.01, y=0.99, xanchor='left', yanchor='top'),
    )

    fig.update_layout(hovermode='x unified')

    if width < 886:
        fig.update_layout(margin={'b': 100})
    else:
        fig.update_layout(margin={'b': 20})

    figure = {'data': fig.data, 'layout': fig.layout}
    # printl(all_data)
    return figure


@app.callback(
    Output('month-selector', 'style'),
    Output('year-selector', 'style'),
    Output('day-selector', 'style'),
    [
        Input('month-button', 'n_clicks_timestamp'),
        Input('year-button', 'n_clicks_timestamp'),
        Input('total-button', 'n_clicks_timestamp'),
        Input('day-button', 'n_clicks_timestamp'),
    ],
)
def update_dropdown_visibility(
    month_clicks, year_clicks, total_clicks, day_clicks
):
    """
    Atualiza a visibilidade dos seletor de mês, ano e dia com base nos cliques nos botões correspondentes.

    Parameters:
        month_clicks (int): Carimbo de data/hora do último clique no botão "Mês".
        year_clicks (int): Carimbo de data/hora do último clique no botão "Ano".
        total_clicks (int): Carimbo de data/hora do último clique no botão "Total".
        day_clicks (int): Carimbo de data/hora do último clique no botão "Dia".

    Returns:
        month_dropdown_style (dict): Um dicionário contendo as configurações de estilo atualizadas para os seletor de mês.
        year_dropdown_style (dict): Um dicionário contendo as configurações de estilo atualizadas para os seletor de ano.
        day_dropdown_styledict (dict): Um dicionário contendo as configurações de estilo atualizadas para os seletor de dia.
    """
    month_dropdown_style = {'width': '100px', 'visibility': 'visible'}
    year_dropdown_style = {'width': '100px', 'visibility': 'visible'}
    day_dropdown_style = {'width': '100px', 'visibility': 'visible'}

    # Verifica qual botão foi clicado por último e atualiza a visibilidade dos seletor correspondentes
    if (
        month_clicks is not None
        and (year_clicks is None or month_clicks > year_clicks)
        and (total_clicks is None or month_clicks > total_clicks)
        and (day_clicks is None or month_clicks > day_clicks)
    ):
        month_dropdown_style['visibility'] = 'visible'
        year_dropdown_style['visibility'] = 'visible'
        day_dropdown_style['visibility'] = 'hidden'
    elif (
        year_clicks is not None
        and (month_clicks is None or year_clicks > month_clicks)
        and (total_clicks is None or year_clicks > total_clicks)
        and (day_clicks is None or year_clicks > day_clicks)
    ):
        month_dropdown_style['visibility'] = 'hidden'
        year_dropdown_style['visibility'] = 'visible'
        day_dropdown_style['visibility'] = 'hidden'
    elif (
        total_clicks is not None
        and (month_clicks is None or total_clicks > month_clicks)
        and (year_clicks is None or total_clicks > year_clicks)
        and (day_clicks is None or total_clicks > day_clicks)
    ):
        month_dropdown_style['visibility'] = 'hidden'
        year_dropdown_style['visibility'] = 'hidden'
        day_dropdown_style['visibility'] = 'hidden'
    elif (
        day_clicks is not None
        and (month_clicks is None or day_clicks > month_clicks)
        and (year_clicks is None or day_clicks > year_clicks)
        and (total_clicks is None or day_clicks > total_clicks)
    ):
        month_dropdown_style['visibility'] = 'visible'
        year_dropdown_style['visibility'] = 'visible'
        day_dropdown_style['visibility'] = 'visible'

    return month_dropdown_style, year_dropdown_style, day_dropdown_style
