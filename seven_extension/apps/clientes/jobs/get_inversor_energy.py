import base64
import calendar
import hashlib
import hmac
import html
import json
import locale
import os
import re
import time as t
from datetime import date, datetime, time, timedelta
from urllib.parse import parse_qs, quote, urlparse

import growattServer
import pytz
import requests
import urllib3
from apps.clientes.methods import printl, print_debug
from apps.clientes.models import (
    Cliente,
    ClienteInfo,
    Empresa,
    Geracao,
    GeracaoDiaria,
    Inversor,
    RelacaoClienteEmpresa,
)
from dateutil.relativedelta import relativedelta
from django.db import connection, transaction
from django.db.models import Q
from requests import Session
from dotenv import load_dotenv
import string
import random
from typing import Optional

from cryptography.hazmat.primitives import serialization, asymmetric, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

load_dotenv()
GEOCODE_API = os.getenv('GEOCODE_API')

# import para testar os métodos rodando no shell do django
# from apps.clientes.models import Cliente, Geracao, GeracaoDiaria, Inversor, Credencial

LIMITE = 100
BATCH_SIZE = 50


def commit_daily_generation(
    daily_generation: list, cliente_latest_timestamp: dict
):
    """
    Persiste a geração diária na base de dados.

    Este método utiliza uma transação atômica para garantir a integridade dos dados durante o processo de inserção em lote.

    Args:
        daily_generation (list): Uma lista de objetos representando a geração diária de energia.
        cliente_latest_timestamp (dict): Um dicionário contendo clientes como chaves e seus respectivos timestamps mais recentes.

    Returns:
        None
    """
    with transaction.atomic():
        GeracaoDiaria.objects.bulk_create(
            daily_generation,
            update_conflicts=True,
            update_fields=[
                'timestamp',
                'energystamp',
            ],
            unique_fields=('cliente', 'timestamp'),
            batch_size=BATCH_SIZE,
        )
        for cliente, latest_timestamp in cliente_latest_timestamp.items():
            # Tente obter a linha correspondente ao cliente
            cliente_info, created = ClienteInfo.objects.get_or_create(
                cliente=cliente
            )

            # Verifique se a linha já existe e se latest_timestamp é mais recente
            if not created:
                if cliente_info.ultima_geracao_diaria:
                    if latest_timestamp > cliente_info.ultima_geracao_diaria:
                        # Se a linha já existir e latest_timestamp for mais recente, atualize ultima_geracao_diaria
                        cliente_info.ultima_geracao_diaria = latest_timestamp
                        cliente_info.save()
                else:
                    # Se a linha já existe e ultima_geracao_diaria for None, defina ultima_geracao_diaria
                    cliente_info.ultima_geracao_diaria = latest_timestamp
                    cliente_info.save()
            elif created:
                # Se a linha foi criada agora, defina ultima_geracao_diaria
                cliente_info.ultima_geracao_diaria = latest_timestamp
                cliente_info.save()


def commit_complete_generation(
    complete_generation: list, cliente_latest_timestamp: dict
):
    """
    Commit da geração completa de energia para o banco de dados.

    Este método utiliza uma transação atômica para garantir a integridade dos dados durante o processo de inserção em lote.

    Args:
        complete_generation (list): Uma lista de objetos representando a geração completa de energia.
        cliente_latest_timestamp (dict): Um dicionário contendo clientes como chaves e seus respectivos timestamps mais recentes.

    Returns:
        None
    """
    with transaction.atomic():
        Geracao.objects.bulk_create(
            complete_generation,
            update_conflicts=True,
            update_fields=[
                'timestamp',
                'energystamp',
            ],
            unique_fields=('cliente', 'timestamp'),
            batch_size=BATCH_SIZE,
        )
        for cliente, latest_timestamp in cliente_latest_timestamp.items():
            # Tente obter a linha correspondente ao cliente
            cliente_info, created = ClienteInfo.objects.get_or_create(
                cliente=cliente
            )

            # Verifique se a linha já existe e se latest_timestamp é mais recente
            if not created:
                if cliente_info.ultima_geracao:
                    if latest_timestamp > cliente_info.ultima_geracao:
                        # Se a linha já existir e latest_timestamp for mais recente, atualize ultima_geracao
                        cliente_info.ultima_geracao = latest_timestamp
                        cliente_info.save()
                else:
                    # Se a linha já existe e ultima_geracao for None, defina ultima_geracao
                    cliente_info.ultima_geracao = latest_timestamp
                    cliente_info.save()
            elif created:
                # Se a linha foi criada agora, defina ultima_geracao
                cliente_info.ultima_geracao = latest_timestamp
                cliente_info.save()



def is_number(string: str) -> bool:
    """
    Verifica se uma string representa um número decimal.

    Args:
        string (str): A string a ser verificada.

    Returns:
        bool: True se a string pode ser convertida em um número decimal, False caso contrário.
    """
    try:
        float(string)
        return True
    except ValueError:
        return False



def convert_energy_units(energy_unit: str) -> float:
    """
    Converte uma unidade de energia para quilowatts (kW) ou megawatts (MW).

    Examples:
        >>> convert_energy_units('1.5 mWh')
        1_500_000.0
        >>> convert_energy_units(0)
        0
        >>> convert_energy_units('10.5 kwh')
        10_500.0

    Args:
        energy_unit (str): A unidade de energia a ser convertida.

    Returns:
        numver (float): O valor convertido em quilowatts (kW), megawatts (MW) ou watts (W).
    """
    energy_unit = str(energy_unit)

    if ',' in energy_unit:
        energy_unit = energy_unit.replace(',', '.')

    if 'kwh' in energy_unit.lower():
        return float(energy_unit.split()[0]) * 1_000
    elif 'mwh' in energy_unit.lower():
        return float(energy_unit.split()[0]) * 1_000_000
    elif 'wh' in energy_unit.lower():
        if '.' in energy_unit:
            energy_unit = energy_unit.replace('.', '')
        return float(energy_unit.split()[0])
    elif is_number(energy_unit):
        return float(energy_unit)
    else:
        return 0


def commit_clientes(clientes: list, dados: list) -> None:
    """
    Commit das informações dos clientes na base de dados.

    Este método utiliza uma transação atômica para garantir a integridade dos dados durante o processo de inserção e atualização.

    Args:
        clientes (list): Uma lista de objetos representando clientes.
        dados (list): Uma lista de dicionários contendo dados originais.

    Returns:
        None
    """
    with transaction.atomic():
        for cliente in clientes:
            # Tente obter um cliente existente com o mesmo plant_id e plant_name
            obj = Cliente.objects.filter(
                plant_id=cliente.plant_id, plant_name=cliente.plant_name
            ).first()

            if obj is not None:
                # Se o cliente já existir, atualize os campos necessários
                obj.energy_today = cliente.energy_today
                obj.energy_total = cliente.energy_total
                obj.latitude = cliente.latitude
                obj.longitude = cliente.longitude
                obj.save()
            else:
                # Se o cliente não existir, crie um novo
                cliente.save()

                # Encontre a empresa correspondente no dados original
                for planta in dados:
                    if (
                        planta['plant_id'] == cliente.plant_id
                        and planta['plant_name'] == cliente.plant_name
                    ):
                        empresa_id = planta['empresa_id']
                        break

                empresa = Empresa.objects.get(id=empresa_id)

                # Crie a relação com a empresa para o novo cliente
                relacao, _ = RelacaoClienteEmpresa.objects.get_or_create(
                    cliente=cliente, empresa=empresa
                )

        # # Log das consultas SQL
        # for query in connection.queries:
        #     if 'SELECT' in query['sql']:
        #         printl(query['sql'])


def append_clientes(dados: list) -> None:
    """
    Adiciona clientes à lista que será inserida na base de dados com base nos dados fornecidos.

    Args:
        dados (list): Uma lista de dicionários contendo informações sobre clientes.

    Returns:
        None
    """
    clientes = []

    for planta in dados:
        cliente = Cliente(
            inverter=planta['inverter'],
            plant_id=planta['plant_id'],
            plant_name=planta['plant_name'],
            energy_today=convert_energy_units(planta['energy_today']),
            energy_total=convert_energy_units(planta['energy_total']),
            latitude=planta['latitude'] if planta['latitude'] else 0,
            longitude=planta['longitude'] if planta['longitude'] else 0,
        )
        clientes.append(cliente)

    # printl('##########CLIENTES NO APPEND###########', clientes)
    # printl('##########DADOS NO APPEND###########', dados)
    commit_clientes(clientes, dados)



def append_complete_generation(dados: dict) -> None:
    """
    Adiciona dados de geração completa à lista que será inserida na base de dados.

    Este método cria objetos de geração completa a partir dos dados fornecidos e os adiciona à base de dados.

    Args:
        dados (dict): Um dicionário contendo informações sobre a geração completa.
        
    Returns:
        None
    """
    complete_generation = []

    unique_values = set()
    timestamp = ''
    energystamp = 0
    cliente_latest_timestamp = (
        {}
    )  # Dicionário para armazenar o último timestamp por cliente

    new_timezone = pytz.timezone('America/Sao_Paulo')

    for item in dados:

        if item['date'].date() != datetime.today().date():
            date = item['date']
            if date.tzinfo is None:
                aware_datetime = new_timezone.localize(date)
            else:
                aware_datetime = date.astimezone(new_timezone)

            cliente = item['cliente']
            timestamp = aware_datetime
            energystamp = convert_energy_units(item['generation'])

            generation = Geracao(
                cliente=cliente,
                timestamp=aware_datetime,
                energystamp=energystamp,
            )

            if (cliente, timestamp) not in unique_values:
                complete_generation.append(generation)
                unique_values.add((cliente, timestamp))

                # Atualize o último timestamp para o cliente atual
                if energystamp is not None and energystamp != 0:
                    if cliente not in cliente_latest_timestamp:
                        cliente_latest_timestamp[cliente] = timestamp
                    elif timestamp > cliente_latest_timestamp[cliente]:
                        cliente_latest_timestamp[cliente] = timestamp

    commit_complete_generation(complete_generation, cliente_latest_timestamp)


def append_daily_generation(dados: dict) -> None:
    """
    Adiciona dados de geração diária à lista que será inserida na base de dados.

    Este método cria objetos de geração diária a partir dos dados fornecidos e os adiciona à base de dados.

    Args:
        dados (dict): Um dicionário contendo informações sobre a geração diária.

    Returns:
        None
    """
    daily_generation = []
    unique_values = set()
    timestamp = ''
    energystamp = 0
    cliente_latest_timestamp = (
        {}
    )  # Dicionário para armazenar o último timestamp por cliente

    for item in dados:

        date = item['date']
        new_timezone = pytz.timezone('America/Sao_Paulo')

        if date.tzinfo is None:
            aware_datetime = new_timezone.localize(date)
        else:
            aware_datetime = date.astimezone(new_timezone)

        cliente = item['cliente']
        timestamp = aware_datetime
        energystamp = convert_energy_units(item['generation'])

        generation = GeracaoDiaria(
            cliente=cliente,
            timestamp=aware_datetime,
            energystamp=energystamp,
        )

        if (cliente, timestamp) not in unique_values:
            daily_generation.append(generation)
            unique_values.add((cliente, timestamp))

            # TODO: Otimizar velocidade, não fazer em cada linha

            # Atualize o último timestamp para o cliente atual
            if energystamp is not None and energystamp != 0:
                if cliente not in cliente_latest_timestamp:
                    cliente_latest_timestamp[cliente] = timestamp
                elif timestamp > cliente_latest_timestamp[cliente]:
                    cliente_latest_timestamp[cliente] = timestamp
                # print(cliente_latest_timestamp)

    # Envie daily_generation e cliente_latest_timestamp para a função commit_daily_generation
    commit_daily_generation(daily_generation, cliente_latest_timestamp)


def hash_password(password: str) -> str:
    """
    Encripta uma senha usando o algoritmo SHA-256.

    Args:
        password (str): A senha para encriptar.

    Returns:
        str: A senha encriptada.
    """
    # Convert the password to bytes.
    password_bytes = password.encode()

    # Create a hash object.
    hash_object = hashlib.sha256()

    # Hash the password.
    hash_object.update(password_bytes)

    # Return the hash value.
    return hash_object.hexdigest()


def buscar_ultima_informacao_diaria(cliente):
    """
    Busca a última informação diária de geração para um cliente.

    Este método verifica se há uma entrada na tabela ClienteInfo para o cliente fornecido.
    
    Se existir, retorna a data da última geração diária registrada.
    
    Caso contrário, tenta buscar a informação diretamente na tabela GeracaoDiaria.
    
    Se encontrar registros com energystamp > 0, retorna a data do último registro.
    
    Caso contrário, cria uma linha fictícia e retorna a data desta linha.

    Args:
        cliente: O cliente para o qual buscar a última informação diária.

    Returns:
        datetime or False: A data da última informação diária, ou False se não houver registros.

    """
    try:
        ultima_informacao = ClienteInfo.objects.get(
            Q(cliente__plant_id=cliente.plant_id)
            & Q(cliente__plant_name=cliente.plant_name)
        )
        ultimo_dia = (
            ultima_informacao.ultima_geracao_diaria
            if ultima_informacao
            else False
        )

    except ClienteInfo.DoesNotExist:
        try:
            t.sleep(5)
            queryset = GeracaoDiaria.objects.filter(
                Q(cliente__plant_id=cliente.plant_id)
                & Q(cliente__plant_name=cliente.plant_name)
                & Q(energystamp__gt=0)
            )
            # printl(str(queryset.query))
            # Verifique se há registros no queryset
            if queryset.exists():
                ultima_informacao = queryset.latest('timestamp')
                ultimo_dia = ultima_informacao.timestamp
            else:
                # Se não houver registros com energystamp > 0, crie uma linha fictícia
                ultimo_dia = datetime(2001, 1, 1)
                ultimo_dia = ultimo_dia.replace(
                    tzinfo=pytz.timezone('America/Sao_Paulo')
                )

            ClienteInfo.objects.update_or_create(
                cliente=cliente, defaults={'ultima_geracao_diaria': ultimo_dia}
            )

        except GeracaoDiaria.DoesNotExist:
            # Se não houver registros, crie uma linha fictícia
            ultimo_dia = datetime(2001, 1, 1)
            ultimo_dia = ultimo_dia.replace(
                tzinfo=pytz.timezone('America/Sao_Paulo')
            )
            ClienteInfo.objects.update_or_create(
                cliente=cliente, defaults={'ultima_geracao_diaria': ultimo_dia}
            )
            ultimo_dia = False

    return ultimo_dia


def buscar_ultima_informacao_completa(cliente):
    """
    Busca a data da última informação completa de geração para um cliente.

    Este método verifica se há uma entrada na tabela ClienteInfo para o cliente fornecido.
    
    Se existir, retorna a data da última geração completa registrada.
    
    Caso contrário, tenta buscar a informação diretamente na tabela Geracao.
    
    Se encontrar registros com energystamp > 0, retorna a data do último registro.
    
    Caso contrário, cria uma linha fictícia e retorna a data desta linha.

    Args:
        cliente: O cliente para o qual buscar a última informação completa.

    Returns:
        datetime.date or False: A data da última informação completa, ou False se não houver registros.

    """
    try:
        ultima_informacao = ClienteInfo.objects.get(
            Q(cliente__plant_id=cliente.plant_id)
            & Q(cliente__plant_name=cliente.plant_name)
        )
        if ultima_informacao and ultima_informacao.ultima_geracao is not None:
            ultimo_dia = ultima_informacao.ultima_geracao.date()
        else:
            ultimo_dia = False

    except ClienteInfo.DoesNotExist:
        try:
            t.sleep(5)
            queryset = Geracao.objects.filter(
                Q(cliente__plant_id=cliente.plant_id)
                & Q(cliente__plant_name=cliente.plant_name)
                & Q(energystamp__gt=0)
            )

            # Verifique se há registros no queryset
            if queryset.exists():
                ultima_informacao = queryset.latest('timestamp')
                ultimo_dia = ultima_informacao.timestamp.date()
            else:
                # Se não houver registros com energystamp > 0, crie uma linha fictícia
                ultimo_dia = datetime(2001, 1, 1).date()
                ultimo_dia = ultimo_dia.replace(
                    tzinfo=pytz.timezone('America/Sao_Paulo')
                )

            ClienteInfo.objects.update_or_create(
                cliente=cliente, defaults={'ultima_geracao': ultimo_dia}
            )

        except Geracao.DoesNotExist:
            # Se não houver registros, crie uma linha fictícia
            ultimo_dia = datetime(2001, 1, 1).date()
            ultimo_dia = ultimo_dia.replace(
                tzinfo=pytz.timezone('America/Sao_Paulo')
            )
            ClienteInfo.objects.update_or_create(
                cliente=cliente, defaults={'ultima_geracao': ultimo_dia}
            )
            ultimo_dia = False

    return ultimo_dia


def login_growatt(data: dict):
    """
    Realiza o login em um sistema Growatt.

    Este método cria uma sessão, adiciona cabeçalhos ao User-Agent, configura os dados de login
    com o nome de usuário e senha fornecidos, e realiza uma solicitação POST para a URL de login.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.
        
            Deve incluir as chaves 'sess', 'api_url', 'username', e 'password'.

    """
    data['sess'] = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81'
    }
    data['sess'].headers.update(headers)
    data['data_login'] = {
        'account': data['username'],
        'password': data['password'],
    }

    data['sess'].post(data['api_url'] + 'login', data['data_login'])

    return data


def atualiza_clientes_growatt(data: dict) -> None:
    """
    Atualiza informações de clientes do sistema Growatt.

    Este método envia solicitações para obter a lista de plantas e, em seguida, para obter informações detalhadas de cada planta.
    Com base nas informações obtidas, são gerados dicionários de clientes que são posteriormente enviados para o método 'append_clientes'.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            Deve incluir as chaves 'sess', 'api_url', 'empresa_id', entre outras necessárias.

    Returns:
        None

    """
    data['data'] = {
        'currPage': '1',
        'plantType': '-1',
        'orderType': '2',
        'plantName': '',
    }

    try:
        response = data['sess'].post(
            data['api_url'] + 'selectPlant/getPlantList', data['data']
        )
    except json.JSONDecodeError as e:
        print(f'Ocorreu um erro ao decodificar o JSON - Growatt: {e}')
        print(response.json())

    clientes = []

    # Obtenha o número total de páginas na primeira resposta
    total_pages = response.json()['pages']

    # Itere sobre todas as páginas
    for page in range(1, total_pages + 1):
        # Atualize a página atual na solicitação de dados
        data['data']['currPage'] = str(page)

        # Envie a solicitação
        response = data['sess'].post(
            data['api_url'] + 'selectPlant/getPlantList', data['data']
        )

        # Gere o dicionário de plantas
        for plant in response.json()['datas']:
            data['json_data'] = {'plantId': plant['id']}
            # print(plant['id'])

            response_interno = data['sess'].post(
                data['api_url'] + 'plantbC/plantInfo/getPlantTotal',
                data['json_data'],
            )

            if response_interno.status_code != 500:
                energy_total = (
                    f"{response_interno.json()['obj']['eTotal']} kwh"
                )
                latitude = response_interno.json()['obj']['plant_lat']
                longitude = response_interno.json()['obj']['plant_lng']
            else:
                energy_total = 0
                latitude = 0
                longitude = 0

            cliente = {
                'inverter': Inversor.objects.get(name='growatt'),
                'plant_id': plant['id'],
                'plant_name': plant['plantName'],
                'energy_today': f"{plant['eToday']} kwh",
                'energy_total': energy_total,
                'latitude': latitude,
                'longitude': longitude,
                'empresa_id': data['empresa_id'],
            }
            clientes.append(cliente)

    append_clientes(clientes)


def atualiza_geracao_growatt(data: dict) -> None:
    """
    Atualiza as informações de geração de energia para clientes Growatt.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Growatt. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Growatt.
            
            - clientes (list): Lista de objetos cliente Growatt.

    Returns:
        None

    """
    generation = []
    generation_complete_enumerate = []

    max_empty_months = 4

    for cliente in data['clientes']:

        empty_months = 0

        day = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while empty_months < max_empty_months:

            if encerrar_loop:
                break

            data['data'] = {'plantId': cliente.plant_id}

            response = data['sess'].post(
                data['api_url'] + 'panel/getDevicesByPlant', data=data['data']
            )
            tipo_instalacao = ''

            if 'obj' in response.json():
                obj = response.json()['obj']
                if 'max' in obj:
                    tlxSn = obj['max'][0][0]
                    tipo_instalacao = 'comercial'
                elif 'tlx' in obj:
                    tlxSn = obj['tlx'][0][0]
                    tipo_instalacao = 'residencial'
                    data['data']['tlxSn'] = tlxSn
                else:
                    printl('ERRO INTERNO NO JSON', response.json())
                    break
            else:
                printl('ERRO EXTERNO NO JSON', response.json())

            data['data']['date'] = day.strftime('%Y-%m')

            try:
                if tipo_instalacao == 'comercial':
                    response = data['sess'].post(
                        data['api_url'] + 'indexbC/inv/getInvEnergyMonthChart',
                        data=data['data'],
                    )
                    printl('JSON COMERCIAL ID', cliente.plant_id, data['data'])
                    printl('JSON COMERCIAL', response.json())
                    registros = response.json()['obj'].get('energy')
                else:
                    response = data['sess'].post(
                        data['api_url'] + 'panel/tlx/getTLXEnergyMonthChart',
                        data=data['data'],
                    )
                    printl(
                        'JSON RESIDENCIAL ID', cliente.plant_id, data['data']
                    )
                    printl('JSON RESIDENCIAL', response.json())
                    registros = response.json()['obj']['charts'].get('energy')
            except json.decoder.JSONDecodeError:
                # Se ocorrer um erro ao decodificar o JSON, faça algo aqui
                printl('Erro ao decodificar o JSON GROWATT', response.text)

            printl(cliente.plant_name, data['data'], empty_months)

            # t.sleep(5)
            # printl(response.json())

            if not registros:
                break

            if all(item is None or item == 0.0 for item in registros):
                empty_months += 1
            else:
                empty_months = 0

            # Iterar sobre os dados de energia
            for dia, energy in enumerate(registros, start=1):

                # Obtenha o ano e o mês de 'day'
                year = day.year
                month = day.month

                # Crie um objeto datetime para o dia do mês
                date = datetime(year, month, dia)

                # Crie o dicionário com a data e a geração de energia
                geracao_completa = {
                    'date': date,
                    'generation': energy,
                }

                # Adicione o dicionário à lista
                generation_complete_enumerate.append(geracao_completa)

            # Ordenando a lista de tuplas pelo primeiro elemento em ordem decrescente
            sorted_data = sorted(
                generation_complete_enumerate,
                key=lambda x: x['date'],
                reverse=True,
            )
            generation_complete_enumerate = []

            for dados in sorted_data:
                data_obj = dados['date']
                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break

                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f"{dados['generation']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            day -= relativedelta(months=1)

    append_complete_generation(generation)


def atualiza_geracao_diaria_growatt(data: dict) -> None:
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Growatt.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Growatt. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Growatt.
            
            - clientes (list): Lista de objetos cliente Growatt.

    Returns:
        None

    """

    generation_day = []
    generation_day_enumerate = []
    max_empty_days = 60

    for cliente in data['clientes']:

        empty_days = 0

        day = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while empty_days < max_empty_days:
            if encerrar_loop:
                break

            data['data'] = {
                'plantId': cliente.plant_id,
                'date': day.strftime('%Y-%m-%d'),
            }
            # t.sleep(2)
            # printl(cliente.plant_name, data['data'], empty_days)
            response = data['sess'].post(
                data['api_url'] + 'indexbC/inv/getInvEnergyDayChart',
                data=data['data'],
            )
            # t.sleep(10)
            # printl(cliente.plant_name, response.json())
            if not response.json()['obj'].get('pac'):
                break

            # Suponha que 'pac' é a lista de 288 registros
            registros = response.json()['obj'].get('pac')
            # Verifique se todos os registros são None
            if all(item is None for item in registros):
                empty_days += 1
            else:
                empty_days = 0
            # printl(response.json())
            # Data inicial (meia-noite do dia atual)
            start_time = datetime.strptime(
                day.strftime('%Y-%m-%d'), '%Y-%m-%d'
            )

            # Iterar sobre os dados de geração de energia
            for i, generation in enumerate(response.json()['obj']['pac']):

                # Calcular o timestamp para este intervalo de tempo
                timestamp = start_time + timedelta(minutes=i * 5)

                # Criar o objeto GeracaoDiaria
                geracao_diaria = {
                    'date': timestamp,
                    'generation': generation,
                }

                # Adicionar à lista
                generation_day_enumerate.append(geracao_diaria)
            # printl(generation_day_enumerate)
            # Ordenando a lista de tuplas pelo primeiro elemento em ordem decrescente
            sorted_data = sorted(
                generation_day_enumerate, key=lambda x: x['date'], reverse=True
            )
            generation_day_enumerate = []
            # printl(sorted_data)
            for dados in sorted_data:
                dia = dados['date']
                # printl(cliente.plant_id, ultimo_dia, dia)
                if ultimo_dia and (
                    dia.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break
                generation_day.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': dia,
                        'generation': dados['generation'],
                        'cliente': cliente,
                    }
                )
                if len(generation_day) > LIMITE:
                    append_daily_generation(generation_day)
                    generation_day = []
            day -= relativedelta(days=1)

    append_daily_generation(generation_day)

# TODO: Getting these values directly from the files by the Sungrow API is better than hardcoding them...
LOGIN_RSA_PUBLIC_KEY: asymmetric.rsa.RSAPublicKey = serialization.load_pem_public_key(b"-----BEGIN PUBLIC KEY-----\nMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDJRGV7eyd9peLPOIqFg3oionWqpmrjVik2wyJzWqv8it3yAvo/o4OR40ybrZPHq526k6ngvqHOCNJvhrN7wXNUEIT+PXyLuwfWP04I4EDBS3Bn3LcTMAnGVoIka0f5O6lo3I0YtPWwnyhcQhrHWuTietGC0CNwueI11Juq8NV2nwIDAQAB\n-----END PUBLIC KEY-----")
APP_RSA_PUBLIC_KEY: asymmetric.rsa.RSAPublicKey   = serialization.load_pem_public_key(bytes("-----BEGIN PUBLIC KEY-----\n" + "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCkecphb6vgsBx4LJknKKes-eyj7-RKQ3fikF5B67EObZ3t4moFZyMGuuJPiadYdaxvRqtxyblIlVM7omAasROtKRhtgKwwRxo2a6878qBhTgUVlsqugpI_7ZC9RmO2Rpmr8WzDeAapGANfHN5bVr7G7GYGwIrjvyxMrAVit_oM4wIDAQAB".replace("-", "+").replace("_", "/") + "\n-----END PUBLIC KEY-----",  'utf8'))
ACCESS_KEY = "9grzgbmxdsp3arfmmgq347xjbza4ysps"
APP_KEY = "B0455FBE7AA0328DB57B59AA729F05D8"

def encrypt_rsa(value: str, key: asymmetric.rsa.RSAPublicKey) -> str:
    # Encrypt the value
    encrypted = key.encrypt(
        value.encode(),
        asymmetric.padding.PKCS1v15(),
    )
    return base64.b64encode(encrypted).decode()

def encrypt_aes(data: str, key: str):
    key_bytes = key.encode('utf-8')
    data_bytes = data.encode('utf-8')

    # Ensure the key is 16 bytes (128 bits)
    if len(key_bytes) != 16:
        raise ValueError("Key must be 16 characters long")

    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data_bytes) + padder.finalize()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return encrypted_data.hex()

def decrypt_aes(data: str, key: str):
    key_bytes = key.encode('utf-8')

    # Ensure the key is 16 bytes (128 bits)
    if len(key_bytes) != 16:
        raise ValueError("Key must be 16 characters long")

    encrypted_data = bytes.fromhex(data)
    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
    return decrypted_data.decode('utf-8')

def generate_random_word(length: int):
    char_pool = string.ascii_letters + string.digits
    random_word = ''.join(random.choice(char_pool) for _ in range(length))
    return random_word

class SungrowScraper:
    def __init__(self, username: str, password: str):
        self.baseUrl = "https://www.isolarcloud.com"
        # TODO: Set the gateway during the login procedure
        self.gatewayUrl = "https://gateway.isolarcloud.com.hk"
        self.username = username
        self.password = password
        self.session: "requests.Session" = requests.session()
        self.userToken: "str|None" = None
        #TODO: Alterar orgId para contemplar também userId
        self.userId: "int|None" = None

    def login(self):
        self.session = requests.session()
        resp = self.session.post(
            f"{self.baseUrl}/userLoginAction_login",
            data={
                "userAcct": self.username,
                "userPswd": encrypt_rsa(self.password, LOGIN_RSA_PUBLIC_KEY),
            },
            headers={
                "_isMd5": "1"
            },
            timeout=60,
        )
        #print(resp.json())
        self.userToken = resp.json()["user_token"]
        return self.userToken

    def post(self, relativeUrl: str, jsn: "Optional[dict]"=None, isFormData=False):
        userToken = self.userToken if self.userToken is not None else self.login()
        jsn = dict(jsn) if jsn is not None else {}
        nonce = generate_random_word(32)
        # TODO: Sungrow also adjusts for time difference between server and client
        # This is probably not a must though. The relevant call is:
        # https://gateway.isolarcloud.eu/v1/timestamp
        unixTimeMs = int(t.time() * 1000)
        jsn["api_key_param"] = {"timestamp": unixTimeMs, "nonce": nonce}
        randomKey = "web" + generate_random_word(13)
        userToken = self.userToken
        userId = userToken.split('_')[0]
        jsn["user_id"] = userId
        jsn["appkey"] = APP_KEY
        if "token" not in jsn:
            jsn["token"] = userToken
        jsn["sys_code"] = 200
        jsn["lang"] = "_pt_BR"
        data: "dict|str"
        if isFormData:
            jsn["api_key_param"] = encrypt_aes(json.dumps(jsn["api_key_param"]), randomKey)
            jsn["appkey"] = encrypt_aes(jsn["appkey"], randomKey)
            jsn["token"] = encrypt_aes(jsn["token"], randomKey)
            data = jsn
        else:
            data = encrypt_aes(json.dumps(jsn, separators=(",", ":")), randomKey)
        #print(f"{self.gatewayUrl}{relativeUrl}", jsn)
        resp = self.session.post(
            f"{self.gatewayUrl}{relativeUrl}",
            data=data,
            headers={
                "x-access-key": ACCESS_KEY,
                "x-random-secret-key": encrypt_rsa(randomKey, APP_RSA_PUBLIC_KEY),
                "x-limit-obj": encrypt_rsa(userId, APP_RSA_PUBLIC_KEY),
                "content-type": "application/json;charset=UTF-8"
            },
            #verify=False  # Desativar verificação SSL
        )
        return decrypt_aes(resp.text, randomKey)


def login_sungrow(data):
    """
    Realiza o login no sistema Sungrow e obtém as informações necessárias para futuras solicitações.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.
        
            Deve incluir as chaves 'username', 'password', 'api_url', entre outras necessárias.

    Returns:
        None

    """
    
    data['s'] = SungrowScraper(data['username'], data['password'])
    data['json'] = {
        "share_type_list": ["0", "1", "2"]
    }
    

def atualiza_clientes_sungrow(data):
    """
    Atualiza a lista de clientes no sistema Sungrow com informações mais recentes.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            Deve incluir as chaves 'api_url', 'json', 'empresa_id', entre outras necessárias.

    Returns:
        None

    """
    clientes = []

    response = data['s'].post(
        '/v1/powerStationService/getPsList',
        #jsn=data['json'],
    )
    response = json.loads(response)
    #print_debug(f'Valor da variável: {response}')
    plants = response['result_data']['pageList']

    for plant in plants:
        cliente = {
            'inverter': Inversor.objects.get(name='sungrow'),
            'plant_id': plant['ps_id'],
            'plant_name': plant['ps_name'],
            'energy_today': f'{plant["today_energy"]["value"]} {plant["today_energy"]["unit"]}',
            'energy_total': f'{plant["total_energy"]["value"]} {plant["total_energy"]["unit"]}',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)
    #printl(clientes)
    # Chama a função para adicionar os clientes ao banco de dados
    append_clientes(clientes)


def atualiza_geracao_diaria_sungrow(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Sungrow.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Sungrow. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Sungrow.
            
            - clientes (list): Lista de objetos cliente Sungrow.

    Returns:
        None

    """
    # TODO: Lembrar de alterar 'data' para trazer o id do cliente, para facilitar a busca
    generation_day = []

    max_empty_days = 90

    for cliente in data['clientes']:

        empty_days = 0

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while empty_days < max_empty_days:

            if encerrar_loop == True:
                break

            formatted_date = dia.strftime('%Y%m%d')

            data['json'].update(
                {
                    'ps_id': cliente.plant_id,
                    'date_id': formatted_date,
                    'date_type': '1',
                }
            )

            response = data['s'].post(
                '/v1/powerStationService/getHouseholdStoragePsReport',
                jsn=data['json'],
            )
            response = json.loads(response)

            if not response['result_data']['day_data']['point_data_15_list']:
                empty_days += 1

            else:
                empty_days = 0
                # Ordenando a lista de tuplas pelo primeiro elemento em ordem decrescente
                sorted_data = sorted(
                    response['result_data']['day_data']['point_data_15_list'],
                    key=lambda x: x['time_stamp'],
                    reverse=True,
                )
                for energy in sorted_data:
                    data_obj = datetime.strptime(
                        energy['time_stamp'], '%Y%m%d%H%M%S'
                    )
                    if ultimo_dia and (
                        data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                        < (ultimo_dia - timedelta(hours=2))
                    ):
                        encerrar_loop = True
                        break
                    generation_day.append(
                        {
                            'plant_id': cliente.plant_id,
                            'plant_name': cliente.plant_name,
                            'date': data_obj,
                            'generation': energy['p83076'],
                            'cliente': cliente,
                        }
                    )
                    if len(generation_day) > LIMITE:
                        append_daily_generation(generation_day)
                        generation_day = []
            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_sungrow(data):
    """
    Atualiza as informações de geração de energia para clientes Sungrow.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Sungrow. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Sungrow.
            
            - clientes (list): Lista de objetos cliente Sungrow.

    Returns:
        None
    """

    generation = []

    max_empty_months = 4

    for cliente in data['clientes']:

        empty_months = 0

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while empty_months < max_empty_months:

            if encerrar_loop:
                break

            formatted_date = dia.strftime('%Y%m')

            data['json'].update(
                {
                    'ps_id': cliente.plant_id,
                    'date_id': formatted_date,
                    'date_type': '2',
                }
            )

            response = data['s'].post(
                '/v1/powerStationService/getHouseholdStoragePsReport',
                jsn=data['json'],
            )
            response = json.loads(response)

            if not response['result_data']['month_data'][
                'month_data_day_list'
            ]:
                empty_months += 1
            else:
                empty_months = 0

                for item in response['result_data']['month_data'][
                    'month_data_day_list'
                ]:
                    item['date_id'] = datetime.strptime(
                        str(item['date_id']), '%Y%m%d'
                    )

                # Ordenando a lista de tuplas pelo primeiro elemento em ordem decrescente
                sorted_data = sorted(
                    response['result_data']['month_data'][
                        'month_data_day_list'
                    ],
                    key=lambda x: x['date_id'],
                    reverse=True,
                )

                for day in sorted_data:

                    data_obj = day['date_id']

                    if ultimo_dia and (
                        data_obj.date() < (ultimo_dia - timedelta(days=2))
                    ):
                        encerrar_loop = True
                        break

                    generation.append(
                        {
                            'plant_id': cliente.plant_id,
                            'plant_name': cliente.plant_name,
                            'date': data_obj,
                            'generation': day['p83022'],
                            'cliente': cliente,
                        }
                    )
                    if len(generation) > LIMITE:
                        append_complete_generation(generation)
                        generation = []
            dia -= relativedelta(months=1)

    append_complete_generation(generation)


# TODO: Goodwe vai precisar de um token. Verificar e ajustar futuramente.


def login_abb_fimer(data):
    """
    Realiza o login no sistema ABB Fimer.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.
        
            Deve incluir as chaves 'api_url', 'username' e 'password', entre outras necessárias.

    Returns:
        None

    """
    data['sess'] = requests.Session()

    params = {
        'setCookie': 'true',
    }

    # Faz uma solicitação GET para realizar o login com autenticação básica
    data['sess'].get(
        f'{data["api_url"]}/ums/v1/login',
        params=params,
        auth=(data['username'], data['password']),
    )


def atualiza_clientes_abb_fimer(data):
    """
    Atualiza os dados dos clientes do sistema ABB Fimer.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            Deve incluir as chaves 'api_url', 'sess', 'empresa_id', entre outras necessárias.

    Returns:
        None

    """
    clientes = []
    api_url = data['api_url']
    plants = []

    # Obtém informações sobre as plantas associadas ao usuário autenticado
    response = data['sess'].get(
        f'{api_url}/ums/v1/users/me/info',
    )

    my_id = response.json()['portfolioEntityId']

    response = data['sess'].get(
        f'{api_url}/asset/v1/portfolios/{my_id}/plants?includePerformanceProfiles=true',
    )

    for plant in response.json():
        plants.append(
            {
                'id': plant['entityID'],
                'name': plant['name'],
                'latitude': plant['location']['latitude'],
                'longitude': plant['location']['longitude'],
            }
        )

    tz = pytz.timezone('America/Sao_Paulo')

    now = datetime.now(tz)

    sdt = now.replace(
        year=now.year - 10, hour=00, minute=00, second=0, microsecond=1
    )
    today = now.replace(hour=00, minute=00, second=0, microsecond=1)
    edt = now.replace(hour=23, minute=59, second=59, microsecond=00)

    formatted_today = today.isoformat()
    formatted_sdt = sdt.isoformat()
    formatted_edt = edt.isoformat()

    params = {
        'agp': 'All',
        'afx': 'Delta',
        'sdt': formatted_today,
        'edt': formatted_edt,
    }

    for plant in plants:

        # Obtém a energia gerada hoje para cada planta
        response = data['sess'].get(
            f'{api_url}/telemetry/v1/plants/{plant["id"]}/energy/GenerationEnergy',
            params=params,
        )

        if response.json()[0]:
            plant['energy_today'] = response.json()[0].get('value', 0)

    params = {
        'agp': 'All',
        'afx': 'Delta',
        'sdt': formatted_sdt,
        'edt': formatted_edt,
    }

    for plant in plants:
        # Obtém a energia total gerada para cada planta no período selecionado
        response = data['sess'].get(
            f'{api_url}/telemetry/v1/plants/{plant["id"]}/energy/GenerationEnergy',
            params=params,
        )
        plant['energy_total'] = response.json()[0].get('value', 0)

        cliente = {
            'inverter': Inversor.objects.get(name='abb_fimer'),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': f'{plant["energy_today"]} kwh',
            'energy_total': f'{plant["energy_total"]} kwh',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)

    append_clientes(clientes)


def atualiza_geracao_diaria_abb_fimer(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes ABB Fimer.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes ABB Fimer. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API ABB Fimer.
            
            - clientes (list): Lista de objetos cliente ABB Fimer.

    Returns:
        None

    """
    generation_day = []

    max_empty_days = 90

    for cliente in data['clientes']:

        empty_days = 0

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while empty_days < max_empty_days:

            if encerrar_loop == True:
                break

            formatted_today = dia.strftime('%Y-%m-%d')

            params = {
                'agp': 'Min15',
                'afx': 'Avg',
                'sdt': f'{formatted_today}T00:00:00.000Z',
                'edt': f'{formatted_today}T23:59:59.999Z',
            }

            def busca_geracao_diaria() -> requests.Response:
                """
                Busca informações de geração diária para um cliente específico.

                Esta função realiza até 10 tentativas de obter informações de geração diária
                para um cliente específico da API ABB FIMER. Caso obtenha sucesso, retorna a
                resposta da requisição. Se ocorrer um erro 502, a função tenta reconectar-se
                através da função login_abb_fimer().

                Args:
                    data (dict): Um dicionário contendo informações necessárias para a busca.
                    
                        - sess (requests.Session): Sessão para realizar as requisições.
                        
                        - api_url (str): URL da API ABB FIMER.
                        
                    cliente (Cliente): Um objeto cliente específico para o qual deseja-se obter as informações.

                Returns:
                    requests.Response: Resposta da requisição HTTP para a API ABB FIMER.

                Raises:
                    Exception: Se ocorrer um erro durante as tentativas de requisição.

                """

                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        response = data['sess'].get(
                            f'{data["api_url"]}/telemetry/v1/plants/{cliente.plant_id}/power/GenerationPower',
                            params=params,
                        )
                        if response.status_code == 502:
                            raise Exception('Erro 502.')
                        else:
                            break
                    except Exception as e:
                        print(
                            f'ABB FIMER - Geração diária. Ocorreu um erro: {e}'
                        )
                        login_abb_fimer()
                    tentativas += 1

                return response

            response = busca_geracao_diaria()

            soma_dia = 0

            try:
                sorted_data = sorted(
                    response.json(), key=lambda x: x['start'], reverse=True
                )
            except:
                print(response.json())

            for item in sorted_data:
                if 'value' not in item:
                    item['value'] = 0

                soma_dia += float(item['value'])
                data_obj = datetime.strptime(
                    item['start'], '%Y-%m-%dT%H:%M:%S%z'
                )
                if ultimo_dia and (
                    data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break
                generation_day.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': item['value'],
                        'cliente': cliente,
                    }
                )
                if len(generation_day) > LIMITE:
                    append_daily_generation(generation_day)
                    generation_day = []

            if soma_dia == 0:
                empty_days += 1
            else:
                empty_days = 0

            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_abb_fimer(data):
    """
    Atualiza as informações de geração de energia para clientes ABB Fimer.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes ABB Fimer. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API ABB Fimer.
            
            - clientes (list): Lista de objetos cliente ABB Fimer.

    Returns:
        None
    """

    generation = []

    max_empty_months = 4

    for cliente in data['clientes']:

        empty_months = 0

        tz = pytz.timezone('America/Sao_Paulo')

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while empty_months < max_empty_months:

            if encerrar_loop:
                break

            _, last_day = calendar.monthrange(dia.year, dia.month)
            first_day_of_month = dia.replace(day=1)

            last_day_of_month = dia.replace(day=last_day)

            start_time = tz.localize(
                datetime.combine(first_day_of_month, time.min)
            )
            end_time = tz.localize(
                datetime.combine(last_day_of_month, time.max)
            )

            utc_start_time = start_time.astimezone(pytz.utc)
            utc_end_time = end_time.astimezone(pytz.utc)

            sdt = utc_start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            edt = utc_end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            params = {
                'agp': 'Day',
                'afx': 'Delta',
                'sdt': sdt,
                'edt': edt,
            }

            response = data['sess'].get(
                f'{data["api_url"]}/telemetry/v1/plants/{cliente.plant_id}/energy/GenerationEnergy',
                params=params,
            )

            soma_dia = 0

            sorted_data = sorted(
                response.json(), key=lambda x: x['start'], reverse=True
            )

            for item in sorted_data:
                if 'value' not in item:
                    item['value'] = 0
                data_obj = datetime.strptime(
                    item['start'], '%Y-%m-%dT%H:%M:%S%z'
                )
                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break

                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f"{item['value']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
                soma_dia += item['value']

            if soma_dia == 0:
                empty_months += 1
            else:
                empty_months = 0

            dia -= relativedelta(months=1)

    append_complete_generation(generation)


def login_fronius(data):
    """
    Realiza o login no sistema Fronius.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.
        
            Deve incluir as chaves 'api_url', 'sess', 'username', 'password', entre outras necessárias.

    Returns:
        None

    """
    api_url = data['api_url']

    # Inicia uma sessão
    data['sess'] = requests.Session()

    # Obtém o sessionDataKey da página de login
    response = data['sess'].get(f'{api_url}/Account/ExternalLogin')
    match = re.search(r'sessionDataKey=([a-z0-9-]+)', response.text)

    if match:
        sessionDataKey = match.group(1)

    # Prepara os dados para o login
    data['data'] = {
        'sessionDataKey': sessionDataKey,
        'username': data['username'],
        'password': data['password'],
    }

    # Realiza a autenticação
    response = data['sess'].post(
        'https://login.fronius.com/commonauth', data=data['data']
    )

    # Extrai os tokens e informações da resposta
    code_match = re.search(r'name="code"\s*value="(.*?)"', response.text)
    id_token_match = re.search(r'name="id_token"value="(.*?)"', response.text)
    state_match = re.search(r'name="state"value="(.*?)"', response.text)
    AuthenticatedIdPs_match = re.search(
        r'name="AuthenticatedIdPs"value="(.*?)"', response.text
    )
    session_state_match = re.search(
        r'name="session_state"\s*value="(.*?)"', response.text
    )

    # Atribui os valores correspondentes, se encontrados
    if code_match:
        code = code_match.group(1)

    if id_token_match:
        id_token = id_token_match.group(1)

    if state_match:
        state = state_match.group(1)

    if AuthenticatedIdPs_match:
        AuthenticatedIdPs = AuthenticatedIdPs_match.group(1)

    if session_state_match:
        session_state = session_state_match.group(1)

    # Atualiza os dados com os tokens e informações obtidos
    data['data'] = {
        'code': code,
        'id_token': id_token,
        'state': state,
        'AuthenticatedIdPs': AuthenticatedIdPs,
        'session_state': session_state,
    }


def atualiza_clientes_fronius(data):
    """
    Atualiza as informações dos clientes a partir do sistema Fronius.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            Deve incluir as chaves 'api_url', 'sess', 'data' e 'empresa_id', entre outras necessárias.

    Returns:
        None

    """
    api_url = data['api_url']

    # Lista para armazenar informações dos clientes
    clientes = []

    # Lista para armazenar informações das plantas
    plants = []

    # Realiza a autenticação/callback para obter as plantas associadas ao usuário
    data['sess'].post(f'{api_url}/Account/ExternalLoginCallback', data=data['data'])
    response = data['sess'].get(f'{api_url}/PvSystems/GetPvSystemsForListView')

    # Obtém informações básicas das plantas
    for plant in response.json()['data']:
        plants.append(
            {
                'id': plant['PvSystemId'],
                'name': plant['PvSystemName'],
                'latitude': None,
                'longitude': None,
            }
        )

    # Obtém informações detalhadas de cada planta, incluindo localização geográfica
    for plant in plants:
        params = {'pvSystemId': plant['id']}
        response = data['sess'].get(f'{api_url}/PvSystemSettings/PvSystemProfile', params=params)

        rua = re.search(r'<label for="Street">Rua<\/label>.*?value="(.*?)"', response.text, re.DOTALL)
        cep = re.search(r'<label for="ZipCode">CEP<\/label>.*?value="(.*?)"', response.text, re.DOTALL)
        cidade = re.search(r'<label for="City">Cidade<\/label>.*?value="(.*?)"', response.text, re.DOTALL)

        address = f'{rua.group(1)}, {cidade.group(1)}, {cep.group(1)}'
        geo_url = f'https://geocode.maps.co/search?q={address}&api_key={GEOCODE_API}'

        t.sleep(1.1)
        location = requests.get(geo_url.format(address=quote(address)))

        if location.text == '[]':
            address = f'{rua.group(1)}'
            geo_url = f'https://geocode.maps.co/search?q={address}&api_key={GEOCODE_API}'
            t.sleep(1.1)
            location = requests.get(geo_url.format(address=quote(address)))

        plant['latitude'] = 0 if location.text == '[]' else location.json()[0]['lat']
        plant['longitude'] = 0 if location.text == '[]' else location.json()[0]['lon']

    # Obtém informações de produção de cada planta para o dia atual
    dia = datetime.now()
    for plant in plants:
        params = {
            'pvSystemId': plant['id'],
            'year': dia.year,
            'month': dia.month,
            'day': dia.day,
            'interval': 'all',
            'view': 'production',
        }
        response = data['sess'].get(f'{api_url}/Chart/GetChartNew', params=params)
        plant['energy_total'] = response.json()['sumValue']

        params.update({'interval': 'day'})
        response_valor = data['sess'].get(f'{api_url}/Chart/GetChartNew', params=params)
        plant['energy_today'] = response_valor.json()['sumValue']

    # Cria registros de clientes com as informações obtidas
    for plant in plants:
        cliente = {
            'inverter': Inversor.objects.get(name='fronius'),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': plant['energy_today'],
            'energy_total': plant['energy_total'],
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)

    # Adiciona ou atualiza os registros na base de dados
    append_clientes(clientes)


def atualiza_geracao_diaria_fronius(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Fronius.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Fronius. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Fronius.
            
            - clientes (list): Lista de objetos cliente Fronius.

    Returns:
        None

    """
    generation_day = []

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while True:

            if encerrar_loop == True:
                break

            params = {
                'pvSystemId': cliente.plant_id,
                'year': dia.year,
                'month': dia.month,
                'day': dia.day,
                'interval': 'day',
                'view': 'production',
            }

            response = data['sess'].get(
                f'{data["api_url"]}/Chart/GetChartNew', params=params
            )

            if not response.json()['settings']['series']:
                break

            sorted_data = sorted(
                response.json()['settings']['series'][0]['data'],
                key=lambda x: x[0],
                reverse=True,
            )

            for timestamp, energia in sorted_data:
                data_obj = datetime.fromtimestamp(timestamp / 1000)

                if ultimo_dia and (
                    data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break

                generation_day.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': energia,
                        'cliente': cliente,
                    }
                )
                if len(generation_day) > LIMITE:
                    append_daily_generation(generation_day)
                    generation_day = []
            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_fronius(data):
    """
    Atualiza as informações de geração de energia para clientes Fronius.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Fronius. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Fronius.
            
            - clientes (list): Lista de objetos cliente Fronius.

    Returns:
        None
    """
    generation = []

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while True:

            if encerrar_loop:
                break

            params = {
                'pvSystemId': cliente.plant_id,
                'year': dia.year,
                'month': dia.month,
                'day': dia.day,
                'interval': 'month',
                'view': 'production',
            }

            response = data['sess'].get(
                f'{data["api_url"]}/Chart/GetChartNew', params=params
            )
            # print(response.json())
            if not response.json()['settings']['series']:
                break

            sorted_data = sorted(
                response.json()['settings']['series'][0]['data'],
                key=lambda x: x[0],
                reverse=True,
            )

            for timestamp, energia in sorted_data:
                data_obj = datetime.fromtimestamp(timestamp / 1000)
                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break
                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f'{energia} kwh',
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            dia -= relativedelta(months=1)

    append_complete_generation(generation)


def login_refusol(data):
    """
    Realiza o login no sistema Refusol.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.
        
            Deve incluir as chaves 'api_url', 'sess', 'username' e 'password', entre outras necessárias.

    Returns:
        None

    """
    # Desabilita os avisos de certificado SSL não verificado
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Inicializa uma sessão
    data['sess'] = requests.Session()

    # Define o idioma para Português
    data['sess'].cookies.update({'PL': 'pt-PT'})

    # Faz uma requisição GET para obter os valores do VIEWSTATE, VIEWSTATEGENERATOR e EVENTVALIDATION
    response = data['sess'].get(f'{data["api_url"]}/Default.aspx', verify=False)

    # Utiliza expressões regulares para extrair os valores necessários do HTML
    viewstate_match = re.search(r'id="__VIEWSTATE"\s*value="(.*?)"', response.text)
    viewstategenerator_match = re.search(r'id="__VIEWSTATEGENERATOR"\s*value="(.*?)"', response.text)
    eventvalidation_match = re.search(r'id="__EVENTVALIDATION"\s*value="(.*?)"', response.text)

    # Atribui os valores extraídos às variáveis correspondentes
    if viewstate_match:
        viewstate = viewstate_match.group(1)
    if viewstategenerator_match:
        viewstategenerator = viewstategenerator_match.group(1)
    if eventvalidation_match:
        eventvalidation = eventvalidation_match.group(1)

    # Define os dados para a requisição POST de login
    data['data'] = {
        '__EVENTTARGET': '',
        '__EVENTARGUMENT': '',
        '__VIEWSTATE': viewstate,
        '__VIEWSTATEGENERATOR': viewstategenerator,
        '__EVENTVALIDATION': eventvalidation,
        'ctl00$headerControl$loginControl$txtUsername': data['username'],
        'ctl00$headerControl$loginControl$txtPassword': data['password'],
        'ctl00$headerControl$loginControl$btnLogin': 'Login',
    }

    # Faz a requisição POST para efetuar o login
    response = data['sess'].post(f'{data["api_url"]}/Default.aspx', data=data['data'], verify=False)


def get_data_refusol(plant, chart_interval, data, dia):
    """
    Obtém dados do sistema Refusol para um determinado intervalo de gráfico.

    Args:
        plant (dict): Um dicionário contendo informações sobre a planta.
        chart_interval (int): O intervalo do gráfico desejado.
        data (dict): Um dicionário contendo informações adicionais necessárias para a solicitação.
        dia (datetime): Um objeto datetime representando o dia para o qual os dados devem ser obtidos.

    Returns:
        dict: Um dicionário contendo os dados obtidos do sistema Refusol.

    """
    try:
        id = plant['id']
    except (TypeError, KeyError):
        id = plant.plant_id

    data['url'] = f'{data["api_url"]}/Ajax/StatisticsWebService.aspx/GetDataForChannels'
    
    # Configuração dos parâmetros JSON para a solicitação POST
    json = {
        'channels': [
            {
                'ChannelId': 5,
                'ChartData': [],
                'ChartInterval': chart_interval,
                'DataType': 11,
                'IsPlantDataAccessibleBasedOnLicense': True,
                'MeasureUnit': 5,
                'MeasureUnitCode': 'kWh',
                'SolarObject': {
                    'Firmware': None,
                    'Id': id,
                    'Type': 0,
                },
                'Visible': True,
            }
        ],
        'year': dia.year,
        'month': dia.month,
        'day': dia.day,
    }
    
    # Faz a solicitação POST para obter os dados
    response = data['sess'].post(data['url'], json=json, verify=False)
    
    # Retorna os dados no formato JSON
    return response.json()


def atualiza_clientes_refusol(data):
    """
    Atualiza os clientes do sistema Refusol com dados de produção de energia.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização dos clientes.

    Returns:
        None

    """
    dia = datetime.now()

    clientes = []
    plants = []

    # Configuração dos parâmetros para a solicitação POST
    data['data'] = {
        'publicMap': 'False',
        'accountId': 6586,
        # TODO: Aqui precisa ser ajustado para pegar automaticamente o accountId
        'isMapAdmin': 'False',
        'selectedIconsType': 0,
    }

    # Faz a solicitação POST para obter as informações das plantas
    response = data['sess'].post(
        f'{data["api_url"]}/Ajax/RenderMapScript.aspx/GetGoogleMapMarkers',
        json=data['data'],
        verify=False,
    )

    # Coleta informações sobre as plantas
    for plant in response.json()['d']:
        plants.append(
            {
                'name': plant['PlantName'],
                'id': plant['PlantID'],
                'latitude': plant['Latitude'],
                'longitude': plant['Longitude'],
            }
        )

    # Itera sobre cada planta para obter dados de produção de energia
    for plant in plants:

        # Obtém dados de produção de energia para o intervalo diário
        data['data'] = get_data_refusol(plant, 1, data, datetime.now())
        for item in data['data']['d'][0]['ChartData']:
            if item['DateTime']['Day'] == dia.day:
                plant['energy_today'] = item['Value']['Value1']
                break
        plant.setdefault('energy_today', 0)

        # Calcula a soma total de energia para o intervalo mensal
        soma = 0
        data['data'] = get_data_refusol(plant, 3, data, datetime.now())
        for item in data['data']['d'][0]['ChartData']:
            soma += item['Value']['Value1']
        plant['energy_total'] = soma

    # Cria objetos Cliente e os adiciona à lista de clientes
    for plant in plants:
        cliente = {
            'inverter': Inversor.objects.get(name='refusol'),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': f'{plant["energy_today"]} kwh',
            'energy_total': f'{plant["energy_total"]} kwh',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)

    # Adiciona os clientes atualizados ao sistema
    append_clientes(clientes)


def atualiza_geracao_diaria_refusol(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Refusol.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Refusol. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Refusol.
            
            - clientes (list): Lista de objetos cliente Refusol.

    Returns:
        None

    """
    generation_day = []
    empty_days = 0
    max_empty_days = 360

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while True:

            if encerrar_loop == True:
                break

            json = {
                'channels': [
                    {
                        'ChannelId': 1,
                        'ChartData': [],
                        'ChartInterval': 0,
                        'DataType': 4,
                        'IsPlantDataAccessibleBasedOnLicense': True,
                        'MeasureUnit': 0,
                        'MeasureUnitCode': 'W',
                        'SolarObject': {
                            'Firmware': None,
                            'Id': cliente.plant_id,
                            'Type': 0,
                        },
                        'Visible': True,
                    }
                ],
                'year': dia.year,
                'month': dia.month,
                'day': dia.day,
            }

            response = data['sess'].post(data['url'], json=json, verify=False)
            try:
                response_data = response.json()['d'][0]['ChartData']
            except json.JSONDecodeError as e:
                print(f'Ocorreu um erro ao decodificar o JSON: {e}')
                print(response.json())

            if any(
                item['DateTime']['Day'] == dia.day
                and item['DateTime']['Month'] == dia.month
                and item['DateTime']['Year'] == dia.year
                for item in response_data
            ):
                empty_days = 0
            else:
                empty_days += 1

            if empty_days >= max_empty_days:
                break

            for item in response_data:

                if item['DateTime']['Day'] == dia.day:
                    data_obj = datetime.strptime(
                        f"{item['DateTime']['Year']}:{item['DateTime']['Month']}:{item['DateTime']['Day']} {item['DateTime']['Hour']}:{item['DateTime']['Minute']}",
                        '%Y:%m:%d %H:%M',
                    )
                    if ultimo_dia and (
                        data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                        < (ultimo_dia - timedelta(hours=2))
                    ):
                        encerrar_loop = True
                        break
                    generation_day.append(
                        {
                            'plant_id': cliente.plant_id,
                            'plant_name': cliente.plant_name,
                            'date': data_obj,
                            'generation': item['Value']['Value1'],
                            'cliente': cliente,
                        }
                    )
                    if len(generation_day) > LIMITE:
                        append_daily_generation(generation_day)
                        generation_day = []

            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_refusol(data):
    """
    Atualiza as informações de geração de energia para clientes Refusol.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Refusol. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Refusol.
            
            - clientes (list): Lista de objetos cliente Refusol.

    Returns:
        None
    """

    generation = []
    max_empty_months = 12
    empty_months = 0

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while True:

            if encerrar_loop:
                break

            data['data'] = get_data_refusol(cliente, 1, data, dia)
            response_data = data['data']['d'][0]['ChartData']
            if any(
                item['DateTime']['Day'] == dia.day
                and item['DateTime']['Month'] == dia.month
                and item['DateTime']['Year'] == dia.year
                for item in response_data
            ):
                empty_months = 0
            else:
                empty_months += 1

            if empty_months >= max_empty_months:
                break

            def get_data(item: dict) -> datetime:
                """
                Converte dados de data fornecidos em um dicionário para um objeto datetime.

                Args:
                    item (dict): Dicionário contendo informações sobre a data.
                    
                        - 'DateTime' (dict): Dicionário com chaves 'Year', 'Month' e 'Day'
                        representando ano, mês e dia, respectivamente.

                Returns:
                    datetime: Objeto datetime representando a data extraída do dicionário.

                Example:
                    >>> data_info = {'DateTime': {'Year': 2023, 'Month': 11, 'Day': 17}}
                    >>> get_data(data_info)
                    datetime.datetime(2023, 11, 17, 0, 0)
                """
                data_str = f"{item['DateTime']['Year']}:{item['DateTime']['Month']}:{item['DateTime']['Day']}"
                data_obj = datetime.strptime(data_str, '%Y:%m:%d')
                return data_obj

            sorted_data = sorted(response_data, key=get_data, reverse=True)

            for item in sorted_data:
                data_obj = datetime.strptime(
                    f"{item['DateTime']['Year']}:{item['DateTime']['Month']}:{item['DateTime']['Day']}",
                    '%Y:%m:%d',
                )
                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break
                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f"{item['Value']['Value1']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            dia -= relativedelta(months=1)

    append_complete_generation(generation)


def login_deye(data):
    """
    Realiza o login no sistema DEYE para obter um token de acesso.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.

    Returns:
        None

    Raises:
        Exception: Se ocorrer um erro durante o processo de login, printa e tenta novamente.

    """
    tentativa = 0
    max_tentativas = 10

    while tentativa < max_tentativas:

        try:

            data['sess'] = requests.Session()

            data['json'] = {
                'grant_type': 'mdc_password',
                'identity_type': '2',
                'username': data['username'],
                'password': data['hashed_password'],
                'clear_text_pwd': data['password'],
                'client_id': 'test',
                'password_type': '',
                'system': 'SOLARMAN',
                'businessArea': 'FOREIGN_1',
                'businessSubArea': 'SA',
            }

            data['headers'] = {
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 OPR/100.0.0.0',
            }

            response = data['sess'].post(
                f'{data["api_url"]}/oauth-s/oauth/token',
                data=data['json'],
                headers=data['headers'],
            )

            access_token = response.json()['access_token']
            data['headers']['Authorization'] = f'Bearer {access_token}'
            data['json'] = {
                'language': 'pt',
            }
            response = data['sess'].get(
                f'{data["api_url"]}/user-s/acc/org/my?language=pt',
                headers=data['headers'],
            )
            data['json'] = {
                'grant_type': 'mdc_password',
                'identity_type': '2',
                'username': data['username'],
                'password': data['hashed_password'],
                'access_token': 'access_token',
                'clear_text_pwd': data['password'],
                'client_id': 'test',
                'org_id': response.json()[0]['org']['id'],
                'system': 'SOLARMAN',
            }

            response = data['sess'].post(
                f'{data["api_url"]}/oauth-s/oauth/token',
                data=data['json'],
                headers=data['headers'],
            )

            access_token = response.json()['access_token']
            data['headers']['Authorization'] = f'Bearer {access_token}'

            break

        except Exception as e:
            print(e)
            tentativa += 1
            t.sleep(5)


def atualiza_clientes_deye(data):
    """
    Atualiza informações dos clientes DEYE e os adiciona à base de dados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.

    Returns:
        None

    """
    clientes = []

    data['params'] = {
        # TODO:  Ajustar para verificar as demais páginas
        'page': '1',
        'size': '200',
        'order.direction': 'ASC',
        'order.property': 'name',
    }

    data['json'] = {'station': {'powerTypeList': ['PV']}}

    response = data['sess'].post(
        f'{data["api_url"]}/maintain-s/operating/station/v2/search',
        params=data['params'],
        headers=data['headers'],
        json=data['json'],
    )

    plants = []

    for plant in response.json()['data']:

        date = datetime.fromtimestamp(plant['station']['lastUpdateTime'])
        date = date.day, date.month, date.year
        today = datetime.now()
        today = today.day, today.month, today.year

        energy_today = (
            plant['station']['generationValue'] if date == today else 0
        )

        plants.append(
            {
                'id': plant['station']['id'],
                'name': plant['station']['name'],
                'energy_total': plant['station'][
                    'generationUploadTotalOffset'
                ],
                'energy_today': energy_today,
                'latitude': plant['station']['locationLat'],
                'longitude': plant['station']['locationLng'],
            }
        )

    for plant in plants:

        cliente = {
            'inverter': Inversor.objects.get(name=data['inversor']),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': f'{plant["energy_today"]} kwh',
            'energy_total': f'{plant["energy_total"]} kwh',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)

    append_clientes(clientes)


def atualiza_geracao_diaria_deye(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Deye.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Deye. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Deye.
            
            - clientes (list): Lista de objetos cliente Deye.

    Returns:
        None

    """
    generation_day = []
    LIMITE = 50
    # print('clientes', data['clientes'])
    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while True:

            if encerrar_loop == True:
                break

            params = {
                'year': dia.year,
                'month': dia.month,
                'day': dia.day,
            }

            def busca_geracao_diaria():
                """
                Realiza tentativas de busca de dados de geração diária.

                Returns:
                    response.json() (dict): Dicionário contendo os dados de geração diária, conforme a resposta da API.

                Raises:
                    Exception: Erro genérico em caso de falha na requisição.
                    Exception: Erro 500 se o status da resposta for 500.

                """

                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        response = data['sess'].get(
                            f'{data["api_url"]}/maintain-s/history/power/{cliente.plant_id}/record',
                            params=params,
                            headers=data['headers'],
                        )
                        # print('response text', response.text)
                        if response.status_code == 500:
                            raise Exception(
                                'Deye - Geração diária - Erro 500.'
                            )
                        else:
                            break
                    except Exception as e:
                        print(f'Deye - Geração diária. Ocorreu um erro: {e}')
                        t.sleep(5)
                        login_deye(data)
                    tentativas += 1

                return response.json()

            response_data = busca_geracao_diaria()

            # print('response_data', response_data)

            if 'records' not in response_data:
                try:
                    print(response_data)
                    print(response_data.json())
                except Exception as e:
                    print('erro deye geração diária', e)
                break

            sorted_data = sorted(
                response_data['records'],
                key=lambda x: datetime.fromtimestamp(x['dateTime']),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.fromtimestamp(energy['dateTime'])
                # #DEBUG
                # print(data_obj)
                # t.sleep(1)

                if ultimo_dia and (
                    data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break

                generation_day.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': energy['generationPower'],
                        'cliente': cliente,
                    }
                )
                # #DEBUG
                # print(generation_day)
                # t.sleep(1)

                if len(generation_day) > LIMITE:
                    # print('generation_day', generation_day)
                    append_daily_generation(generation_day)
                    generation_day = []
            t.sleep(0.25)
            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_deye(data):
    """
    Atualiza as informações de geração de energia para clientes Deye.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Deye. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Deye.
            
            - clientes (list): Lista de objetos cliente Deye.

    Returns:
        None
    """

    generation = []
    LIMITE = 50

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while True:

            if encerrar_loop:
                break

            params = {
                'year': dia.year,
                'month': dia.month,
            }

            def busca_geracao_completa():
                """
                Realiza tentativas de busca de dados de geração completa.

                Returns:
                    dict: Dicionário contendo os dados de geração completa, conforme a resposta da API.

                Raises:
                    Exception: Erro genérico em caso de falha na requisição.
                    Exception: Erro 500 se o status da resposta for 500.

                """

                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        response = data['sess'].get(
                            f'{data["api_url"]}/maintain-s/history/power/{cliente.plant_id}/stats/month',
                            params=params,
                            headers=data['headers'],
                        )
                        if response.status_code == 500:
                            raise Exception('Deye - Geração - Erro 500.')
                        else:
                            break
                    except Exception as e:
                        print(f'Deye - Geração. Ocorreu um erro: {e}')
                        t.sleep(5)
                        login_deye(data)
                    tentativas += 1

                return response.json()

            response_data = busca_geracao_completa()

            if 'records' not in response_data:
                try:
                    print(response_data)
                    print(response_data.json())
                except Exception as e:
                    print('erro deye geração completa', e)
                break

            sorted_data = sorted(
                response_data['records'],
                key=lambda x: datetime.strptime(x['acceptDay'], '%Y%m%d'),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.strptime(energy['acceptDay'], '%Y%m%d')

                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break

                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f"{energy['generationValue']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            t.sleep(0.1)
            dia -= relativedelta(months=1)

    append_complete_generation(generation)


def login_canadian(data):
    """
    Realiza o processo de login na plataforma Canadian Solar.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.

    Returns:
        None

    Raises:
        ValueError: Se ocorrer um erro no processo de login.
        Exception: Se ocorrer um erro durante o processo de login, printa e tenta novamente.

    """

    tentativa = 0
    max_tentativas = 10

    while tentativa < max_tentativas:

        try:

            data['sess'] = requests.Session()

            data['sess'].headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 OPR/98.0.0.0'
            }

            response = data['sess'].get(
                f'{data["api_url"]}/region-s/dict/listTimezone'
            )

            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'pt-BR,pt;q=0.9',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'application/json;charset=UTF-8',
                # 'Cookie': 'language=pt',
                'Origin': data['api_url'],
                'Pragma': 'no-cache',
                'Referer': data['api_url'],
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 OPR/98.0.0.0',
                'sec-ch-ua': '"Chromium";v="112", "Not_A Brand";v="24", "Opera GX";v="98"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
            }

            json_data = {
                'channel': 'Web',
                'innerVersion': 310,
                'platform': 'CSI CloudPro',
                'platformCode': 'CSI_CLOUDPRO',
                'type': 1,
                'version': '2.5.3',
            }

            response = requests.post(
                f'{data["api_url"]}/announcement-s/app/upgrade/add-version',
                json=json_data,
                headers=headers,
            )

            set_cookie_header = response.headers.get('Set-Cookie')

            if set_cookie_header:
                for cookie in data['sess'].cookies:
                    if cookie.name == 'acw_tc':
                        cookie.value = response.headers.get(
                            'Set-Cookie'
                        ).split(';')[0]
            else:
                raise ValueError('Erro Canadian - response.headers inválido')

            data['data'] = {
                'channel': 'Web',
                'lan': 'pt',
                'platformCode': 'CSI_CLOUDPRO',
                'startTime': 1686321105242,
                'version': '2.5.3',
            }

            response = data['sess'].post(
                f'{data["api_url"]}/announcement-s/announcement/content',
                data=data['data'],
            )
            data['data'] = {
                'grant_type': 'password',
                'identity_type': '2',
                'username': data['username'],
                'password': data['hashed_password'],
                'clear_text_pwd': data['password'],
                'client_id': 'test',
            }

            response = data['sess'].post(
                f'{data["api_url"]}/oauth-s/oauth/token', data=data['data']
            )

            if 'access_token' in response.json():
                data['sess'].headers['Authorization'] = (
                    'Bearer ' + response.json()['access_token']
                )

            else:
                print('erro canadian', response)
                raise ValueError('Erro Canadian - access_token indisponível')

            data['sess'].cookies['tokenKey'] = response.json()['access_token']
            data['sess'].cookies['refreshTokenKey'] = response.json()[
                'refresh_token'
            ]

            params = {'language': 'pt'}
            response = data['sess'].get(
                f'{data["api_url"]}/user-s/acc/org/my', params=params
            )

            data['data']['org_id'] = response.json()[0]['org']['id']

            response = data['sess'].post(
                f'{data["api_url"]}/oauth-s/oauth/token',
                data=data['data'],
            )

            data['sess'].headers['Authorization'] = (
                'Bearer ' + response.json()['access_token']
            )
            data['sess'].cookies['tokenKey'] = response.json()['access_token']
            data['sess'].cookies['refreshTokenKey'] = response.json()[
                'refresh_token'
            ]
            break

        except Exception as e:
            print(e)
            tentativa += 1
            t.sleep(5)


def atualiza_clientes_canadian(data):
    """
    Atualiza a lista de clientes a partir da plataforma Canadian Solar.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.

    Returns:
        None

    """

    clientes = []

    params = {
        # TODO:  Ajustar para verificar as demais páginas
        'page': '1',
        'size': '200',
        'order.direction': 'ASC',
        'order.property': 'name',
    }

    json = {
        'powerTypeList': [
            'PV',
        ],
    }

    response = data['sess'].post(
        f'{data["api_url"]}/maintain-s/operating/station/search',
        params=params,
        # headers=headers,
        json=json,
    )
    plants = []

    for plant in response.json()['data']:

        date = datetime.fromtimestamp(plant['lastUpdateTime'])
        date = date.day, date.month, date.year
        today = datetime.now()
        today = today.day, today.month, today.year

        energy_today = plant['generationValue'] if date == today else 0

        plants.append(
            {
                'id': plant['id'],
                'name': plant['name'],
                'energy_total': plant['generationUploadTotalOffset'],
                'energy_today': energy_today,
                'latitude': plant['locationLat'],
                'longitude': plant['locationLng'],
            }
        )

    for plant in plants:

        cliente = {
            'inverter': Inversor.objects.get(name=data['inversor']),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': f'{plant["energy_today"]} kwh',
            'energy_total': f'{plant["energy_total"]} kwh',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)
        # print(data['inversor'], cliente)

    append_clientes(clientes)


def atualiza_geracao_diaria_canadian(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Canadian.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Canadian. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Canadian.
            
            - clientes (list): Lista de objetos cliente Canadian.

    Returns:
        None

    """
    generation_day = []
    LIMITE = 50

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while True:

            if encerrar_loop == True:
                break

            params = {
                'year': dia.year,
                'month': dia.month,
                'day': dia.day,
            }

            def busca_geracao_diaria():
                """
                Realiza tentativas de busca de dados de geração diária.

                Returns:
                    dict: Dicionário contendo os dados de geração diária, conforme a resposta da API.

                Raises:
                    Exception: Erro genérico em caso de falha na requisição.
                    Exception: Erro 500 se o status da resposta for 500.

                """

                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        response = data['sess'].get(
                            f'{data["api_url"]}/maintain-s/history/power/{cliente.plant_id}/record',
                            params=params,
                        )
                        if response.status_code == 500:
                            raise Exception(
                                'Canadian - Geração diária - Erro 500.'
                            )
                        else:
                            break
                    except Exception as e:
                        print(
                            f'Canadian - Geração diária. Ocorreu um erro: {e}'
                        )
                        t.sleep(5)
                        login_canadian(data)
                    tentativas += 1

                return response.json()

            response_data = busca_geracao_diaria()

            if 'records' not in response_data:
                try:
                    print(response_data)
                    print(response_data.json())
                except Exception as e:
                    print('erro canadian geração diária', e)
                break

            sorted_data = sorted(
                response_data['records'],
                key=lambda x: datetime.fromtimestamp(x['dateTime']),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.fromtimestamp(energy['dateTime'])
                # #DEBUG
                # print(data_obj)
                # t.sleep(1)

                if ultimo_dia and (
                    data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break

                generation_day.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': energy['generationPower'],
                        'cliente': cliente,
                    }
                )
                # #DEBUG
                # print(generation_day)
                # t.sleep(1)

                if len(generation_day) > LIMITE:
                    append_daily_generation(generation_day)
                    generation_day = []
            t.sleep(0.25)
            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_canadian(data):
    """
    Atualiza as informações de geração de energia para clientes Canadian.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Canadian. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Canadian.
            
            - clientes (list): Lista de objetos cliente Canadian.

    Returns:
        None
    """
    generation = []
    LIMITE = 50

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while True:

            if encerrar_loop:
                break

            params = {
                'year': dia.year,
                'month': dia.month,
            }

            def busca_geracao_completa():
                """
                Realiza tentativas de busca de dados de geração completa.

                Returns:
                    dict: Dicionário contendo os dados de geração completa, conforme a resposta da API.

                Raises:
                    Exception: Erro genérico em caso de falha na requisição.
                    Exception: Erro 500 se o status da resposta for 500.

                """

                tentativas = 0
                max_tentativas = 10

                while tentativas < max_tentativas:
                    try:
                        response = data['sess'].get(
                            f'{data["api_url"]}/maintain-s/history/power/{cliente.plant_id}/stats/month',
                            params=params,
                        )
                        if response.status_code == 500:
                            raise Exception('Canadian - Geração - Erro 500.')
                        else:
                            break
                    except Exception as e:
                        print(f'Canadian - Geração. Ocorreu um erro: {e}')
                        t.sleep(5)
                        login_canadian(data)
                    tentativas += 1

                return response.json()

            response_data = busca_geracao_completa()

            if 'records' not in response_data:
                try:
                    print(response_data)
                    print(response_data.json())
                except Exception as e:
                    print('erro canadian geração completa', e)
                break

            sorted_data = sorted(
                response_data['records'],
                key=lambda x: datetime.strptime(x['acceptDay'], '%Y%m%d'),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.strptime(energy['acceptDay'], '%Y%m%d')

                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break

                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f"{energy['generationValue']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            t.sleep(0.1)
            dia -= relativedelta(months=1)

    append_complete_generation(generation)


def login_ecosolys(data):
    """
    Realiza o processo de login na plataforma Ecosolys.

    Este método utiliza o fluxo de autorização OAuth 2.0 com PKCE (Proof Key for Code Exchange).
    
    Ele realiza as seguintes etapas:
    
    1. Inicia uma sessão e desabilita os avisos de segurança relacionados a solicitações inseguras.
    
    2. Gera um código desafiador (code_challenge) e um código de estado (state).
    
    3. Inicia o processo de autorização obtendo um código de autorização do usuário.
    
    4. Autentica o usuário no provedor de identidade (Ecosolys) utilizando as credenciais fornecidas.
    
    5. Obtém um código de autorização redirecionado.
    
    6. Troca o código de autorização por um token de acesso.
    
    7. Define o token de acesso nos cabeçalhos da sessão para autenticação subsequente.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.

    Returns:
        None

    Raises:
        AssertionError: Se a URL de redirecionamento não corresponder à URI esperada.

    """
    # Inicia uma sessão e desabilita os avisos de segurança.
    data['sess'] = requests.Session()
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Configurações iniciais.
    client_id = 'ecosolyspwa'
    redirect_uri = 'https://portal.ecosolys.com.br/home/home'

    # Gera um código desafiador (code_challenge) e um código de estado (state).
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    code_challenge = code_challenge.replace('=', '')
    state = 'fooobarbaz'

    # Inicia o processo de autorização obtendo um código de autorização do usuário.
    response = data['sess'].get(
        data['provider'] + '/auth',
        params={
            'response_type': 'code',
            'client_id': client_id,
            'scope': 'openid',
            'redirect_uri': redirect_uri,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        },
        allow_redirects=False,
    )

    # Extrai a URL de ação do formulário.
    form_action = html.unescape(
        re.search(
            '<form\s+.*?\s+action="(.*?)"', response.text, re.DOTALL
        ).group(1)
    )

    # Autentica o usuário no provedor de identidade.
    response = data['sess'].post(
        url=form_action,
        data={
            'username': data['username'],
            'password': data['password'],
        },
        allow_redirects=False,
    )

    # Obtém a URL de redirecionamento e verifica se corresponde à URI esperada.
    redirect = response.headers['Location']
    assert redirect.startswith(redirect_uri)

    # Extrai o código de autorização da URL de redirecionamento.
    query = urlparse(redirect).query
    redirect_params = parse_qs(query)
    auth_code = redirect_params['code'][0]

    # Troca o código de autorização por um token de acesso.
    response = data['sess'].post(
        data['provider'] + '/token',
        data={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'code': auth_code,
            'code_verifier': code_verifier,
        },
        allow_redirects=False,
    )

    # Define o token de acesso nos cabeçalhos da sessão para autenticação subsequente.
    data['sess'].headers['Authorization'] = (
        'Bearer ' + response.json()['access_token']
    )


def atualiza_clientes_ecosolys(data):
    """
    Atualiza informações sobre os clientes (plantas) na plataforma Ecosolys.

    Este método realiza as seguintes etapas:
    
    1. Obtém informações sobre as plantas (clientes) da API Ecosolys.
    
    2. Para cada planta, obtém informações de localização através da API de geocodificação.
    
    3. Obtém dados de geração de energia total e diária para cada planta.

    4. Cria registros de clientes (plantas) com as informações coletadas.
    
    5. Adiciona os registros de clientes à base de dados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.

    Returns:
        None

    """
    # Inicializa a lista de clientes.
    clientes = []

    # Obtém informações sobre as plantas da API Ecosolys.
    response = data['sess'].get(
        f'{data["api_url"]}/api-v1/planta', allow_redirects=False, verify=False
    )

    # Lista para armazenar informações sobre as plantas.
    plants = []

    # TODO: Aqui preciso verificar quando há mais de um inversor

    # Itera sobre as plantas da resposta da API Ecosolys.
    for plant in response.json():
        rua = plant['endereco']
        cep = plant['cep']
        cidade = plant['cidade']
        uf = plant['uf']

        # Constrói o endereço para a API de geocodificação.
        address = f'{rua}, {cidade}, {uf}, {cep}'
        geo_url = f'https://geocode.maps.co/search?q={address}&api_key={GEOCODE_API}'

        # Obtém informações de localização da API de geocodificação.
        t.sleep(1.1)
        location = requests.get(geo_url.format(address=quote(address)))

        # Se a localização não for encontrada, tenta novamente sem UF.
        if location.text == '[]':
            address = f'{rua}, {cidade}'
            geo_url = f'https://geocode.maps.co/search?q={address}&api_key={GEOCODE_API}'
            t.sleep(1.1)
            location = requests.get(geo_url.format(address=quote(address)))

        # Obtém latitude e longitude ou define como 0 se não encontrado.
        latitude = 0 if location.text == '[]' else location.json()[0]['lat']
        longitude = 0 if location.text == '[]' else location.json()[0]['lon']

        # Adiciona informações da planta à lista de plantas.
        plants.append(
            {
                'id': plant['id'],
                'name': plant['nome'].rpartition('-')[0].strip(),
                'inversor': plant['inversores'][0]['id'],
                'latitude': latitude,
                'longitude': longitude,
            }
        )

    # Obtém a data atual formatada como YYYY-MM-DD.
    today = date.today()
    today = today.strftime('%Y-%m-%d')

    # Para cada planta, obtém dados de geração de energia total e diária.
    for plant in plants:
        response = data['sess'].get(
            f'{data["api_url"]}/api-v1/inversor/geracao/total?inversorId={plant["inversor"]}'
        )
        plant['energy_total'] = response.json()['geracaoEnergia']
        response = data['sess'].get(
            f'{data["api_url"]}/api-v1/inversor/geracao/dia?inversorId={plant["inversor"]}&dia={today}'
        )
        plant['energy_today'] = response.json()['geracaoEnergia']

    # Para cada planta, cria registros de clientes.
    for plant in plants:
        cliente = {
            'inverter': Inversor.objects.get(name='ecosolys'),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': f'{plant["energy_today"]} kwh',
            'energy_total': f'{plant["energy_total"]} kwh',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)

    # Adiciona os registros de clientes à base de dados.
    data['plants'] = plants
    append_clientes(clientes)


def atualiza_geracao_ecosolys(data):
    """
    Atualiza as informações de geração de energia para clientes Ecosolys.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Ecosolys. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Ecosolys.
            
            - clientes (list): Lista de objetos cliente Ecosolys.

    Returns:
        None
    """
    generation = []

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while True:

            if encerrar_loop:
                break

            for plant in data['plants']:
                if plant['id'] == int(cliente.plant_id):
                    id_inversor = plant['inversor']

            params = {
                'inversorId': id_inversor,
                'mes': dia.strftime('%Y-%m-%d'),
            }

            response = data['sess'].get(
                f'{data["api_url"]}/api-v1/inversor/geracao/mes',
                params=params,
            )

            if not response.json()['dados']:
                break

            sorted_data = sorted(
                response.json()['dados'],
                key=lambda x: datetime.strptime(x['data'], '%Y-%m-%d'),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.strptime(energy['data'], '%Y-%m-%d')

                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break

                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f"{energy['quantidade']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            dia = dia.replace(day=1)
            dia -= relativedelta(months=1)

    append_complete_generation(generation)


def atualiza_geracao_diaria_ecosolys(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Ecosolys.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Ecosolys. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Ecosolys.
            
            - clientes (list): Lista de objetos cliente Ecosolys.

    Returns:
        None

    """
    # TODO: Adicionar limite de dias em todos eu acho, pra buscar datas mais antigas
    generation_day = []

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while True:

            if encerrar_loop == True:
                break

            for plant in data['plants']:
                if plant['id'] == int(cliente.plant_id):
                    id_inversor = plant['inversor']

            params = {
                'inversorId': id_inversor,
                'dia': dia.strftime('%Y-%m-%d'),
            }

            response = data['sess'].get(
                f'{data["api_url"]}/api-v1/inversor/geracao/dia',
                params=params,
            )

            if not response.json()['dados']:
                break

            sorted_data = sorted(
                response.json()['dados'],
                key=lambda x: datetime.strptime(x['data'], '%Y-%m-%dT%H:%M'),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.strptime(energy['data'], '%Y-%m-%dT%H:%M')

                if ultimo_dia and (
                    data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break

                generation_day.append(
                    {
                        'plant_id': plant['id'],
                        'plant_name': plant['name'],
                        'date': data_obj,
                        'generation': f"{energy['quantidade']} kwh",
                        'cliente': cliente,
                    }
                )
                if len(generation_day) > LIMITE:
                    append_daily_generation(generation_day)
                    generation_day = []
            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def apply_q_b(value):
    """
    Aplica uma transformação específica aos bits de uma representação binária.

    Esta função recebe uma string representando um número binário e aplica uma
    transformação específica aos seus bits. Cada bit é invertido (0 para 1 e
    1 para 0) e, em seguida, adicionado 2 ao resultado final.

    Args:
        value (str): Uma string representando um número binário.

    Returns:
        str: Uma nova string representando o resultado da transformação.
        
    Note:
        Esta função é a replicação exata do javascript de login dos sistemas Solis.
    """
    return ''.join([bin(2 + ~int(char, 2) & 0b1)[2:] for char in value])



def n(e):
    """
    Implementa uma função de hash baseada no algoritmo MD5.

    Esta função recebe uma string de entrada e aplica uma série de operações
    para gerar um hash MD5 codificado em base64.

    Args:
        e (str): A string de entrada para a qual o hash MD5 será gerado.

    Returns:
        str: O hash MD5 codificado em base64 resultante.

    Note:
        Esta função é a replicação exata do javascript de login dos sistemas Solis.
    """
    def t(e, t):
        return e << t | e >> (32 - t)

    def a(e, t):
        n = 0x80000000 & e
        i = 0x80000000 & t
        a = 0x40000000 & e
        r = 0x40000000 & t
        o = (0x3FFFFFFF & e) + (0x3FFFFFFF & t)
        if a & r:
            return 0x80000000 ^ (o ^ n ^ i)
        if a | r:
            if 0x40000000 & o:
                return 0xC0000000 ^ (o ^ n ^ i)
            else:
                return 0x40000000 ^ (o ^ n ^ i)
        else:
            return o ^ n ^ i

    def r(e, t, a):
        return (e & t) | (~e & a)

    def n(e, t, a):
        return (e & a) | (t & ~a)

    def i(e, t, a):
        return e ^ t ^ a

    def o(e, t, a):
        return t ^ (e | ~a)

    def l(e, n, i, o, l, s, _):
        e = a(e, a(a(r(n, i, o), l), _))
        return a(t(e, s), n)

    def s(e, r, i, o, l, s, _):
        e = a(e, a(a(n(r, i, o), l), _))
        return a(t(e, s), r)

    def _(e, r, n, o, l, s, _):
        e = a(e, a(a(i(r, n, o), l), _))
        return a(t(e, s), r)

    def d(e, r, n, i, l, s, _):
        e = a(e, a(a(o(r, n, i), l), _))
        return a(t(e, s), r)

    def c(e):
        a = len(e)
        r = a + 8
        n = (r - r % 64) // 64
        i = 16 * (n + 1)
        o = [0] * i
        l = 0
        s = 0
        while s < a:
            t = (s - s % 4) // 4
            l = s % 4 * 8
            o[t] = o[t] | (ord(e[s]) << l)
            s += 1
        t = (s - s % 4) // 4
        l = s % 4 * 8
        o[t] = o[t] | (0x80 << l)
        o[i - 2] = a << 3
        o[i - 1] = a >> 29
        return o

    def m(e):
        r = ''
        n = ''
        for a in range(4):
            t = e >> 8 * a & 255
            n = '0' + format(t, 'x')
            r += n[-2:]
        return r

    def g(e):
        e = e.replace('\r\n', '\n')
        t = ''
        for a in range(len(e)):
            r = ord(e[a])
            if r < 128:
                t += chr(r)
            elif r > 127 and r < 2048:
                t += chr(r >> 6 | 192)
                t += chr(63 & r | 128)
            else:
                t += chr(r >> 12 | 224)
                t += chr(r >> 6 & 63 | 128)
                t += chr(63 & r | 128)
        return t

    def u(e):
        h = []
        x = 7
        f = 12
        y = 17
        w = 22
        k = 5
        C = 9
        S = 14
        z = 20
        M = 4
        P = 11
        D = 16
        T = 23
        A = 6
        I = 10
        R = 15
        O = 21
        e = g(e)
        h = c(e)
        u = 1732584193
        p = 4023233417
        b = 2562383102
        v = 271733878
        for t in range(0, len(h), 16):
            r = u
            n = p
            i = b
            o = v
            u = l(u, p, b, v, h[t + 0], x, 3614090360)
            v = l(v, u, p, b, h[t + 1], f, 3905402710)
            b = l(b, v, u, p, h[t + 2], y, 606105819)
            p = l(p, b, v, u, h[t + 3], w, 3250441966)
            u = l(u, p, b, v, h[t + 4], x, 4118548399)
            v = l(v, u, p, b, h[t + 5], f, 1200080426)
            b = l(b, v, u, p, h[t + 6], y, 2821735955)
            p = l(p, b, v, u, h[t + 7], w, 4249261313)
            u = l(u, p, b, v, h[t + 8], x, 1770035416)
            v = l(v, u, p, b, h[t + 9], f, 2336552879)
            b = l(b, v, u, p, h[t + 10], y, 4294925233)
            p = l(p, b, v, u, h[t + 11], w, 2304563134)
            u = l(u, p, b, v, h[t + 12], x, 1804603682)
            v = l(v, u, p, b, h[t + 13], f, 4254626195)
            b = l(b, v, u, p, h[t + 14], y, 2792965006)
            p = l(p, b, v, u, h[t + 15], w, 1236535329)
            u = s(u, p, b, v, h[t + 1], k, 4129170786)
            v = s(v, u, p, b, h[t + 6], C, 3225465664)
            b = s(b, v, u, p, h[t + 11], S, 643717713)
            p = s(p, b, v, u, h[t + 0], z, 3921069994)
            u = s(u, p, b, v, h[t + 5], k, 3593408605)
            v = s(v, u, p, b, h[t + 10], C, 38016083)
            b = s(b, v, u, p, h[t + 15], S, 3634488961)
            p = s(p, b, v, u, h[t + 4], z, 3889429448)
            u = s(u, p, b, v, h[t + 9], k, 568446438)
            v = s(v, u, p, b, h[t + 14], C, 3275163606)
            b = s(b, v, u, p, h[t + 3], S, 4107603335)
            p = s(p, b, v, u, h[t + 8], z, 1163531501)
            u = s(u, p, b, v, h[t + 13], k, 2850285829)
            v = s(v, u, p, b, h[t + 2], C, 4243563512)
            b = s(b, v, u, p, h[t + 7], S, 1735328473)
            p = s(p, b, v, u, h[t + 12], z, 2368359562)
            u = _(u, p, b, v, h[t + 5], M, 4294588738)
            v = _(v, u, p, b, h[t + 8], P, 2272392833)
            b = _(b, v, u, p, h[t + 11], D, 1839030562)
            p = _(p, b, v, u, h[t + 14], T, 4259657740)
            u = _(u, p, b, v, h[t + 1], M, 2763975236)
            v = _(v, u, p, b, h[t + 4], P, 1272893353)
            b = _(b, v, u, p, h[t + 7], D, 4139469664)
            p = _(p, b, v, u, h[t + 10], T, 3200236656)
            u = _(u, p, b, v, h[t + 13], M, 681279174)
            v = _(v, u, p, b, h[t + 0], P, 3936430074)
            b = _(b, v, u, p, h[t + 3], D, 3572445317)
            p = _(p, b, v, u, h[t + 6], T, 76029189)
            u = _(u, p, b, v, h[t + 9], M, 3654602809)
            v = _(v, u, p, b, h[t + 12], P, 3873151461)
            b = _(b, v, u, p, h[t + 15], D, 530742520)
            p = _(p, b, v, u, h[t + 2], T, 3299628645)
            u = d(u, p, b, v, h[t + 0], A, 4096336452)
            v = d(v, u, p, b, h[t + 7], I, 1126891415)
            b = d(b, v, u, p, h[t + 14], R, 2878612391)
            p = d(p, b, v, u, h[t + 5], O, 4237533241)
            u = d(u, p, b, v, h[t + 12], A, 1700485571)
            v = d(v, u, p, b, h[t + 3], I, 2399980690)
            b = d(b, v, u, p, h[t + 10], R, 4293915773)
            p = d(p, b, v, u, h[t + 1], O, 2240044497)
            u = d(u, p, b, v, h[t + 8], A, 1873313359)
            v = d(v, u, p, b, h[t + 15], I, 4264355552)
            b = d(b, v, u, p, h[t + 6], R, 2734768916)
            p = d(p, b, v, u, h[t + 13], O, 1309151649)
            u = d(u, p, b, v, h[t + 4], A, 4149444226)
            v = d(v, u, p, b, h[t + 11], I, 3174756917)
            b = d(b, v, u, p, h[t + 2], R, 718787259)
            p = d(p, b, v, u, h[t + 9], O, 3951481745)
            u = a(u, r)
            p = a(p, n)
            b = a(b, i)
            v = a(v, o)
        E = m(u) + m(p) + m(b) + m(v)
        return E

    def p(e):
        t = 0
        a = len(e)
        if a % 2 != 0:
            return None
        a //= 2
        r = []
        for n in range(a):
            i = e[t : t + 2]
            o = int(i, 16)
            if o > 128:
                o -= 256
            r.append(o)
            t += 2
        return r

    def b(e):
        t = bytes([x % 256 for x in e])
        encoded = base64.b64encode(t)
        return encoded.decode('utf-8')

    v = u(e)
    h = b(p(v))
    return h


def t_hash(data_t, data_a):
    """
    Calcula o hash de mensagem usando HMAC-SHA1.

    Esta função utiliza o algoritmo HMAC-SHA1 para gerar um hash de mensagem
    (Message Authentication Code) a partir dos dados fornecidos.

    Args:
        data_t (str): A chave secreta (segredo) para o HMAC-SHA1.
        data_a (str): Os dados de entrada para os quais o hash de mensagem será gerado.

    Returns:
        str: O hash de mensagem gerado usando HMAC-SHA1 e codificado em base64.

    Example:
        >>> t_hash('chave_secreta', 'dados_para_hash')
        '2jmj7l5rSw0yVb/vlWAYkK/YBwk='
        
    Note:
        Esta função é a replicação exata do javascript de login dos sistemas Solis.
    """
    hmac_obj = hmac.new(data_t.encode('utf-8'), data_a.encode('utf-8'), hashlib.sha1)
    return base64.b64encode(hmac_obj.digest()).decode('utf-8').rstrip('\n')


def retrieve_auth(endpoint, e, now):
    """
    Recupera o token de autenticação.

    Esta função recebe informações específicas e utiliza funções de hashing para gerar
    um token de autenticação conforme necessário para realizar solicitações em um
    determinado endpoint.

    Args:
        endpoint (str): O URL do endpoint para o qual o token de autenticação será gerado.
        e (str): Valor utilizado na geração do hash_js.
        now (str): Timestamp utilizado na geração do hash_token.

    Returns:
        str: O token de autenticação gerado para ser incluído nos cabeçalhos das solicitações.

    Example:
        >>> retrieve_auth('https://example.com/api', 'value_e', '2023-11-17T12:00:00')
        'WEB 2424:generated_auth_token'
        
    Note:
        Esta função é a replicação exata do javascript de login dos sistemas Solis.
    """
    num2 = '0101100111111011000001111101110001000100011'
    num2_hash = apply_q_b(num2)
    hash_bin = str(int(num2_hash, 2))   # o

    jiaMi = '01010111010001000110101100110111110000010100'
    jiaMi_hash = apply_q_b(jiaMi)
    hash_jiaMi = str(hex(int(jiaMi_hash, 2))[2:])   # l

    num4 = '00111111101001100101010101110011'
    num4_hash = apply_q_b(num4)
    hash_hex = str(hex(int(num4_hash, 2))[2:])   # s

    hash_js = n(e)   # t
    # now = a
    url = endpoint   # n
    method = 'post'   # i
    concat = hash_bin + hash_jiaMi + hash_hex   # _

    codigo = '2424'
    local = 'WEB'

    hash_token = t_hash(
        concat,
        method.upper()
        + '\n'
        + hash_js
        + '\napplication/json\n'
        + now
        + '\n'
        + url,
    )

    token = f'{local} {codigo}:{hash_token}'
    return token


def login_solis(data):
    """
    Realiza o login no sistema Solis.

    Esta função realiza o processo de login no sistema Solis, utilizando as credenciais
    fornecidas no dicionário 'data'. O processo de login é feito em até 10 tentativas,
    gerando um token CSRF para autenticação nas requisições subsequentes.

    Args:
        data (dict): Um dicionário contendo informações necessárias para o login.
        
            - username (str): Nome de usuário.
            
            - password (str): Senha do usuário.
            
            - api_url (str): URL da API Solis.

    Returns:
        None

    Raises:
        RuntimeError: Se não for possível obter o token CSRF após 10 tentativas.

    """
    max_tentativas = 10
    tentativa = 0

    while tentativa < max_tentativas:

        hashed_password = hashlib.md5(data['password'].encode()).hexdigest()

        json_data = {
            'userInfo': data['username'],
            'passWord': hashed_password,
            'yingZhenType': 1,
            'localTimeZone': -3,
            'language': '9',
        }

        # Define as configurações regionais para inglês
        locale.setlocale(locale.LC_TIME, 'en_US.utf8')

        now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

        json_string = json.dumps(json_data)
        e = json_string.replace(' ', '')

        authorization = retrieve_auth('/user/login2', e, now)

        data['sess'] = requests.Session()

        json_str = json.dumps(json_data, separators=(',', ':'))
        md5_hash = hashlib.md5(json_str.encode('utf-8')).digest()
        content_md5 = base64.b64encode(md5_hash).decode('utf-8')

        data['headers'] = {
            'authorization': authorization,
            'content-md5': content_md5,
            'time': now,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 OPR/97.0.0.0',
        }
        response = data['sess'].post(
            f'{data["api_url"]}/user/login2',
            headers=data['headers'],
            json=json_data,
        )

        if 'csrfToken' in response.json():
            data['token'] = response.json()['csrfToken']
            break
        else:
            print(response.json())
            print(
                f'Erro: csrfToken não encontrado na resposta. Tentativa {tentativa + 1} de {max_tentativas}'
            )
            t.sleep(5)
            tentativa += 1

    else:
        print(
            f'Erro: csrfToken não encontrado após {max_tentativas} tentativas'
        )
        raise RuntimeError('Não foi possível obter o token CSRF após 10 tentativas.')


def atualiza_clientes_solis(data):
    """
    Atualiza a lista de clientes do sistema Solis.

    Esta função realiza uma requisição para obter informações sobre as estações Solis,
    como energia gerada hoje e energia total. Os dados são processados e atualizados
    na lista de clientes.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - token (str): Token CSRF para autenticação.
            
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Solis.
            
            - headers (dict): Cabeçalhos HTTP para as requisições.
            
            - empresa_id (int): ID da empresa.

    Returns:
        None

    """
    clientes = []

    # Define as configurações regionais para inglês
    locale.setlocale(locale.LC_TIME, 'en_US.utf8')

    now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    # TODO: ajustar para quando tiver mais páginas
    json_data = {
        'pageNo': 1,
        'pageSize': 10,
        'states': '0',
        'stationType': '1',
        'localTimeZone': -3,
        'language': '9',
    }

    json_string = json.dumps(json_data)
    e = json_string.replace(' ', '')

    authorization = retrieve_auth('/station/list', e, now)

    json_str = json.dumps(json_data, separators=(',', ':'))
    md5_hash = hashlib.md5(json_str.encode('utf-8')).digest()
    content_md5 = base64.b64encode(md5_hash).decode('utf-8')

    data['headers'].update(
        {
            'token': data['token'],
            'time': now,
            'authorization': authorization,
            'content-md5': content_md5,
        }
    )

    response = data['sess'].post(
        f'{data["api_url"]}/station/list',
        headers=data['headers'],
        json=json_data,
    )

    plants = []
    for plant in response.json()['data']['page']['records']:
        plants.append(
            {
                'id': plant['id'],
                'name': plant['stationName'],
                'energy_today': f'{plant["dayEnergy"]} {plant["dayEnergyStr"]}',
                'energy_total': f'{plant["allEnergy"]} {plant["allEnergyStr"]}',
                'latitude': plant['latitude'],
                'longitude': plant['longitude'],
            }
        )

    for plant in plants:

        cliente = {
            'inverter': Inversor.objects.get(name='solis'),
            'plant_id': plant['id'],
            'plant_name': plant['name'],
            'energy_today': f'{plant["energy_today"]}',
            'energy_total': f'{plant["energy_total"]}',
            'latitude': plant['latitude'],
            'longitude': plant['longitude'],
            'empresa_id': data['empresa_id'],
        }
        clientes.append(cliente)

    append_clientes(clientes)


def atualiza_geracao_diaria_solis(data):
    """
    Atualiza as informações de geração de energia diária (gráfico horário) para clientes Solis.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Solis. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Solis.
            
            - clientes (list): Lista de objetos cliente Solis.

    Returns:
        None

    """
    generation_day = []

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_diaria(cliente)

        while True:

            if encerrar_loop == True:
                break

            # Define as configurações regionais para inglês
            locale.setlocale(locale.LC_TIME, 'en_US.utf8')

            now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

            json_data = {
                'id': cliente.plant_id,
                'language': '9',
                'localTimeZone': -3,
                'money': 'BRL',
                'time': dia.strftime('%Y-%m-%d'),
                'timeZone': -3,
                'version': 1,
            }

            json_string = json.dumps(json_data)
            e = json_string.replace(' ', '')

            authorization = retrieve_auth('/chart/station/day/v2', e, now)

            json_str = json.dumps(json_data, separators=(',', ':'))
            md5_hash = hashlib.md5(json_str.encode('utf-8')).digest()
            content_md5 = base64.b64encode(md5_hash).decode('utf-8')

            data['headers'].update(
                {
                    'token': data['token'],
                    'time': now,
                    'authorization': authorization,
                    'content-md5': content_md5,
                }
            )

            response = data['sess'].post(
                f'{data["api_url"]}/chart/station/day/v2',
                headers=data['headers'],
                json=json_data,
            )

            response_data = response.json()

            if not response_data['data']:
                break

            records = [
                {'power': power, 'time': time}
                for power, time in zip(
                    response_data['data']['power'],
                    response_data['data']['time'],
                )
            ]

            sorted_data = sorted(
                records,
                key=lambda x: datetime.fromtimestamp(
                    x['time'] / 1000.0, data['tz']
                ),
                reverse=True,
            )

            for record in sorted_data:

                energy = record['power']
                timestamp = record['time']

                data_obj = datetime.fromtimestamp(
                    timestamp / 1000.0, data['tz']
                )

                if ultimo_dia and (
                    data_obj.astimezone(pytz.timezone('America/Sao_Paulo'))
                    < (ultimo_dia - timedelta(hours=2))
                ):
                    encerrar_loop = True
                    break

                generation_day.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': energy,
                        'cliente': cliente,
                    }
                )
                if len(generation_day) > LIMITE:
                    append_daily_generation(generation_day)
                    generation_day = []
            dia -= relativedelta(days=1)

    append_daily_generation(generation_day)


def atualiza_geracao_solis(data):
    """
    Atualiza as informações de geração de energia para clientes Solis.

    Esta função realiza requisições para obter informações mensais sobre a geração
    de energia de clientes Solis. Os dados são processados e armazenados.

    Args:
        data (dict): Um dicionário contendo informações necessárias para a atualização.
        
            - sess (requests.Session): Sessão para realizar as requisições.
            
            - api_url (str): URL da API Solis.
            
            - clientes (list): Lista de objetos cliente Solis.

    Returns:
        None
    """
    generation = []

    for cliente in data['clientes']:

        dia = datetime.now()
        encerrar_loop = False

        ultimo_dia = buscar_ultima_informacao_completa(cliente)

        while True:

            if encerrar_loop:
                break

            # Define as configurações regionais para inglês
            locale.setlocale(locale.LC_TIME, 'en_US.utf8')

            now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

            json_data = {
                'id': cliente.plant_id,
                'language': '9',
                'localTimeZone': -3,
                'money': 'BRL',
                'month': dia.strftime('%Y-%m'),
                'timeZone': -3,
                'version': 1,
            }

            json_string = json.dumps(json_data)
            e = json_string.replace(' ', '')

            authorization = retrieve_auth('/chart/station/month', e, now)

            json_str = json.dumps(json_data, separators=(',', ':'))
            md5_hash = hashlib.md5(json_str.encode('utf-8')).digest()
            content_md5 = base64.b64encode(md5_hash).decode('utf-8')

            data['headers'].update(
                {
                    'token': data['token'],
                    'time': now,
                    'authorization': authorization,
                    'content-md5': content_md5,
                }
            )

            response = data['sess'].post(
                f'{data["api_url"]}/chart/station/month',
                headers=data['headers'],
                json=json_data,
            )

            response_data = response.json()

            if not response_data['data']:
                break

            sorted_data = sorted(
                response_data['data'],
                key=lambda x: datetime.fromtimestamp(
                    x['date'] / 1000.0, data['tz']
                ),
                reverse=True,
            )

            for energy in sorted_data:
                data_obj = datetime.fromtimestamp(
                    energy['date'] / 1000.0, data['tz']
                )

                if ultimo_dia and (
                    data_obj.date() < (ultimo_dia - timedelta(days=2))
                ):
                    encerrar_loop = True
                    break

                generation.append(
                    {
                        'plant_id': cliente.plant_id,
                        'plant_name': cliente.plant_name,
                        'date': data_obj,
                        'generation': f'{energy["energy"]} kwh',
                        'cliente': cliente,
                    }
                )
                if len(generation) > LIMITE:
                    append_complete_generation(generation)
                    generation = []
            dia -= relativedelta(months=1)

    append_complete_generation(generation)
