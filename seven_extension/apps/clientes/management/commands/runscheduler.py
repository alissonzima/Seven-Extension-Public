"""
- Essa job roda na inicialização do servidor
- Para interromper o serviço, execute o comando "sudo systemctl stop runscheduler"
- Substitua "stop" por "start" ou "restart" para inicializar o serviço ou reinicializar, respectivamente
- O script de inicialização do systemctl está em "/etc/systemd/system/runscheduler.service"
"""

import logging
import time as t
from datetime import datetime as dt
from datetime import timedelta

import pytz
from apps.clientes.jobs.get_concessionaria_data import *
from apps.clientes.jobs.get_inversor_energy import *
from apps.clientes.models import (
    Cliente,
    CredencialConcessionaria,
    CredencialInversor,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management.base import BaseCommand
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


@util.close_old_connections
def growatt_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Growatt.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Realiza login na plataforma Growatt.
    
    2. Atualiza informações dos clientes Growatt.
    
    3. Obtém a lista de clientes Growatt.
    
    4. Atualiza a geração diária para os clientes Growatt.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Growatt
    credencial = CredencialInversor.objects.filter(
        inversor__name='growatt'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://server.growatt.com/'

    # Realiza o login na plataforma Growatt
    login_growatt(data)

    # Atualiza informações dos clientes Growatt
    atualiza_clientes_growatt(data)

    # Obtém a lista de clientes Growatt
    data['clientes'] = Cliente.objects.filter(inverter__name='growatt')

    # Atualiza a geração diária para os clientes Growatt
    atualiza_geracao_diaria_growatt(data)


@util.close_old_connections
def sungrow_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Sungrow.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Realiza login na plataforma Sungrow.
    
    2. Atualiza informações dos clientes Sungrow.
    
    3. Obtém a lista de clientes Sungrow.
    
    4. Atualiza a geração diária para os clientes Sungrow.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Sungrow
    credencial = CredencialInversor.objects.filter(
        inversor__name='sungrow'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://gateway.isolarcloud.com.hk'

    # Realiza o login na plataforma Sungrow
    login_sungrow(data)

    # Atualiza informações dos clientes Sungrow
    atualiza_clientes_sungrow(data)

    # Obtém a lista de clientes Sungrow
    data['clientes'] = Cliente.objects.filter(inverter__name='sungrow')

    # Atualiza a geração diária para os clientes Sungrow
    atualiza_geracao_diaria_sungrow(data)


@util.close_old_connections
def abb_fimer_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores ABB FIMER.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Realiza login na plataforma ABB FIMER.
    
    2. Atualiza informações dos clientes ABB FIMER.
    
    3. Obtém a lista de clientes ABB FIMER.
    
    4. Atualiza a geração diária para os clientes ABB FIMER.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor ABB FIMER
    credencial = CredencialInversor.objects.filter(
        inversor__name='abb_fimer'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://www.auroravision.net'

    # Realiza o login na plataforma ABB FIMER
    login_abb_fimer(data)

    # Atualiza informações dos clientes ABB FIMER
    atualiza_clientes_abb_fimer(data)

    # Obtém a lista de clientes ABB FIMER
    data['clientes'] = Cliente.objects.filter(inverter__name='abb_fimer')

    # Atualiza a geração diária para os clientes ABB FIMER
    atualiza_geracao_diaria_abb_fimer(data)


@util.close_old_connections
def fronius_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Fronius.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Realiza login na plataforma Fronius.
    
    2. Atualiza informações dos clientes Fronius.
    
    3. Obtém a lista de clientes Fronius.
    
    4. Atualiza a geração diária para os clientes Fronius.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Fronius
    credencial = CredencialInversor.objects.filter(
        inversor__name='fronius'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://www.solarweb.com'

    # Realiza o login na plataforma Fronius
    login_fronius(data)

    # Atualiza informações dos clientes Fronius
    atualiza_clientes_fronius(data)

    # Obtém a lista de clientes Fronius
    data['clientes'] = Cliente.objects.filter(inverter__name='fronius')

    # Atualiza a geração diária para os clientes Fronius
    atualiza_geracao_diaria_fronius(data)


@util.close_old_connections
def refusol_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Refusol.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Realiza login na plataforma Refusol.
    
    2. Atualiza informações dos clientes Refusol.
    
    3. Obtém a lista de clientes Refusol.
    
    4. Atualiza a geração diária para os clientes Refusol.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Refusol
    credencial = CredencialInversor.objects.filter(
        inversor__name='refusol'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://refu-log.com'

    # Realiza o login na plataforma Refusol
    login_refusol(data)

    # Atualiza informações dos clientes Refusol
    atualiza_clientes_refusol(data)

    # Obtém a lista de clientes Refusol
    data['clientes'] = Cliente.objects.filter(inverter__name='refusol')

    # Atualiza a geração diária para os clientes Refusol
    atualiza_geracao_diaria_refusol(data)


@util.close_old_connections
def canadian_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Canadian Solar.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Canadian Solar.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Canadian Solar.
    
    4. Atualiza informações dos clientes Canadian Solar.
    
    5. Obtém a lista de clientes Canadian Solar.
    
    6. Atualiza a geração diária para os clientes Canadian Solar.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Canadian Solar
    credencial = CredencialInversor.objects.filter(
        inversor__name='canadian'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'] = credencial.usuario
    data['password'] = credencial.senha
    data['hashed_password'] = hash_password(credencial.senha)
    data['api_url'] = 'https://monitoring.csisolar.com'
    data['inversor'] = 'canadian'

    # Realiza o login na plataforma Canadian Solar
    login_canadian(data)

    # Atualiza informações dos clientes Canadian Solar
    atualiza_clientes_canadian(data)

    # Obtém a lista de clientes Canadian Solar
    data['clientes'] = Cliente.objects.filter(inverter__name='canadian')

    # Atualiza a geração diária para os clientes Canadian Solar
    atualiza_geracao_diaria_canadian(data)


@util.close_old_connections
def deye_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Deye.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Deye.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Deye.
    
    4. Atualiza informações dos clientes Deye.
    
    5. Obtém a lista de clientes Deye.
    
    6. Atualiza a geração diária para os clientes Deye.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Deye
    credencial = CredencialInversor.objects.filter(
        inversor__name='deye'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'] = credencial.usuario
    data['password'] = credencial.senha
    data['hashed_password'] = hash_password(credencial.senha)
    data['api_url'] = 'https://pro.solarmanpv.com'
    data['inversor'] = 'deye'

    # Realiza o login na plataforma Deye
    login_deye(data)

    # Atualiza informações dos clientes Deye
    atualiza_clientes_deye(data)

    # Obtém a lista de clientes Deye
    data['clientes'] = Cliente.objects.filter(inverter__name='deye')

    # Atualiza a geração diária para os clientes Deye
    atualiza_geracao_diaria_deye(data)


@util.close_old_connections
def ecosolys_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Ecosolys.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Ecosolys.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Ecosolys.
    
    4. Atualiza informações dos clientes Ecosolys.
    
    5. Obtém a lista de clientes Ecosolys.
    
    6. Atualiza a geração diária para os clientes Ecosolys.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Ecosolys
    credencial = CredencialInversor.objects.filter(
        inversor__name='ecosolys'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://portal.ecosolys.com.br:8843'
    data['provider'] = 'https://portal.ecosolys.com.br:9443/auth/realms/ecoSolys/protocol/openid-connect'

    # Realiza o login na plataforma Ecosolys
    login_ecosolys(data)

    # Atualiza informações dos clientes Ecosolys
    atualiza_clientes_ecosolys(data)

    # Obtém a lista de clientes Ecosolys
    data['clientes'] = Cliente.objects.filter(inverter__name='ecosolys')

    # Atualiza a geração diária para os clientes Ecosolys
    atualiza_geracao_diaria_ecosolys(data)


@util.close_old_connections
def solis_hourly_generation():
    """
    Realiza atualizações horárias na geração de energia para os inversores Solis.

    Esta função é agendada para ser executada periodicamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Solis.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Solis.
    
    4. Atualiza informações dos clientes Solis.
    
    5. Obtém a lista de clientes Solis.
    
    6. Atualiza a geração diária para os clientes Solis.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Solis
    credencial = CredencialInversor.objects.filter(
        inversor__name='solis'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://www.soliscloud.com:15555'
    data['tz'] = pytz.timezone('America/Sao_Paulo')

    # Realiza o login na plataforma Solis
    login_solis(data)

    # Atualiza informações dos clientes Solis
    atualiza_clientes_solis(data)

    # Obtém a lista de clientes Solis
    data['clientes'] = Cliente.objects.filter(inverter__name='solis')

    # Atualiza a geração diária para os clientes Solis
    atualiza_geracao_diaria_solis(data)


@util.close_old_connections
def goodwe_hourly_generation():
    ...


@util.close_old_connections
def growatt_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Growatt.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Growatt.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Growatt.
    
    4. Atualiza informações dos clientes Growatt.
    
    5. Obtém a lista de clientes Growatt.
    
    6. Atualiza a geração diária para os clientes Growatt.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Growatt
    credencial = CredencialInversor.objects.filter(
        inversor__name='growatt'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://server.growatt.com/'

    # Realiza o login na plataforma Growatt
    login_growatt(data)

    # Atualiza informações dos clientes Growatt
    atualiza_clientes_growatt(data)

    # Obtém a lista de clientes Growatt
    data['clientes'] = Cliente.objects.filter(inverter__name='growatt')

    # Atualiza a geração diária para os clientes Growatt
    atualiza_geracao_growatt(data)


@util.close_old_connections
def sungrow_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Sungrow.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Sungrow.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Sungrow.
    
    4. Atualiza informações dos clientes Sungrow.
    
    5. Obtém a lista de clientes Sungrow.
    
    6. Atualiza a geração diária para os clientes Sungrow.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Sungrow
    credencial = CredencialInversor.objects.filter(
        inversor__name='sungrow'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://gateway.isolarcloud.com.hk'

    # Realiza o login na plataforma Sungrow
    login_sungrow(data)

    # Atualiza informações dos clientes Sungrow
    atualiza_clientes_sungrow(data)

    # Obtém a lista de clientes Sungrow
    data['clientes'] = Cliente.objects.filter(inverter__name='sungrow')

    # Atualiza a geração diária para os clientes Sungrow
    atualiza_geracao_sungrow(data)


@util.close_old_connections
def abb_fimer_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores ABB FIMER.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor ABB FIMER.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma ABB FIMER.
    
    4. Atualiza informações dos clientes ABB FIMER.
    
    5. Obtém a lista de clientes ABB FIMER.
    
    6. Atualiza a geração diária para os clientes ABB FIMER.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor ABB FIMER
    credencial = CredencialInversor.objects.filter(
        inversor__name='abb_fimer'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://www.auroravision.net'

    # Realiza o login na plataforma ABB FIMER
    login_abb_fimer(data)

    # Atualiza informações dos clientes ABB FIMER
    atualiza_clientes_abb_fimer(data)

    # Obtém a lista de clientes ABB FIMER
    data['clientes'] = Cliente.objects.filter(inverter__name='abb_fimer')

    # Atualiza a geração diária para os clientes ABB FIMER
    atualiza_geracao_abb_fimer(data)


@util.close_old_connections
def fronius_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Fronius.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Fronius.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Fronius.
    
    4. Atualiza informações dos clientes Fronius.
    
    5. Obtém a lista de clientes Fronius.
    
    6. Atualiza a geração diária para os clientes Fronius.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Fronius
    credencial = CredencialInversor.objects.filter(
        inversor__name='fronius'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://www.solarweb.com'

    # Realiza o login na plataforma Fronius
    login_fronius(data)

    # Atualiza informações dos clientes Fronius
    atualiza_clientes_fronius(data)

    # Obtém a lista de clientes Fronius
    data['clientes'] = Cliente.objects.filter(inverter__name='fronius')

    # Atualiza a geração diária para os clientes Fronius
    atualiza_geracao_fronius(data)


@util.close_old_connections
def refusol_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Refusol.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Refusol.
    
    2. Preenche um dicionário de dados com informações necessárias.
    3. Realiza o login na plataforma Refusol.
    
    4. Atualiza informações dos clientes Refusol.
    
    5. Obtém a lista de clientes Refusol.
    
    6. Atualiza a geração diária para os clientes Refusol.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Refusol
    credencial = CredencialInversor.objects.filter(
        inversor__name='refusol'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://refu-log.com'

    # Realiza o login na plataforma Refusol
    login_refusol(data)

    # Atualiza informações dos clientes Refusol
    atualiza_clientes_refusol(data)

    # Obtém a lista de clientes Refusol
    data['clientes'] = Cliente.objects.filter(inverter__name='refusol')

    # Atualiza a geração diária para os clientes Refusol
    atualiza_geracao_refusol(data)


@util.close_old_connections
def canadian_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Canadian Solar.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Canadian Solar.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Canadian Solar.
    
    4. Atualiza informações dos clientes Canadian Solar.
    
    5. Obtém a lista de clientes Canadian Solar.
    
    6. Atualiza a geração diária para os clientes Canadian Solar.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Canadian Solar
    credencial = CredencialInversor.objects.filter(
        inversor__name='canadian'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'] = credencial.usuario
    data['password'] = credencial.senha
    data['hashed_password'] = hash_password(credencial.senha)
    data['api_url'] = 'https://monitoring.csisolar.com'
    data['inversor'] = 'canadian'

    # Realiza o login na plataforma Canadian Solar
    login_canadian(data)

    # Atualiza informações dos clientes Canadian Solar
    atualiza_clientes_canadian(data)

    # Obtém a lista de clientes Canadian Solar
    data['clientes'] = Cliente.objects.filter(inverter__name='canadian')

    # Atualiza a geração diária para os clientes Canadian Solar
    atualiza_geracao_canadian(data)


@util.close_old_connections
def deye_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Deye.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Deye.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Deye.
    
    4. Atualiza informações dos clientes Deye.
    
    5. Obtém a lista de clientes Deye.
    
    6. Atualiza a geração diária para os clientes Deye.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Deye
    credencial = CredencialInversor.objects.filter(
        inversor__name='deye'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'] = credencial.usuario
    data['password'] = credencial.senha
    data['hashed_password'] = hash_password(credencial.senha)
    data['api_url'] = 'https://pro.solarmanpv.com'
    data['inversor'] = 'deye'

    # Realiza o login na plataforma Deye
    login_deye(data)

    # Atualiza informações dos clientes Deye
    atualiza_clientes_deye(data)

    # Obtém a lista de clientes Deye
    data['clientes'] = Cliente.objects.filter(inverter__name='deye')

    # Atualiza a geração diária para os clientes Deye
    atualiza_geracao_deye(data)


@util.close_old_connections
def ecosolys_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Ecosolys.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Ecosolys.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Ecosolys.
    
    4. Atualiza informações dos clientes Ecosolys.
    
    5. Obtém a lista de clientes Ecosolys.
    
    6. Atualiza a geração diária para os clientes Ecosolys.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Ecosolys
    credencial = CredencialInversor.objects.filter(
        inversor__name='ecosolys'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://portal.ecosolys.com.br:8843'
    data['provider'] = 'https://portal.ecosolys.com.br:9443/auth/realms/ecoSolys/protocol/openid-connect'

    # Realiza o login na plataforma Ecosolys
    login_ecosolys(data)

    # Atualiza informações dos clientes Ecosolys
    atualiza_clientes_ecosolys(data)

    # Obtém a lista de clientes Ecosolys
    data['clientes'] = Cliente.objects.filter(inverter__name='ecosolys')

    # Atualiza a geração diária para os clientes Ecosolys
    atualiza_geracao_ecosolys(data)


@util.close_old_connections
def solis_day_generation():
    """
    Realiza atualizações diárias na geração de energia para os inversores Solis.

    Esta função é agendada para ser executada diariamente pelo APScheduler. Ela interage com diferentes
    métodos para realizar as seguintes operações:
    
    1. Obtém as credenciais do inversor Solis.
    
    2. Preenche um dicionário de dados com informações necessárias.
    
    3. Realiza o login na plataforma Solis.
    
    4. Atualiza informações dos clientes Solis.
    
    5. Obtém a lista de clientes Solis.
    
    6. Atualiza a geração diária para os clientes Solis.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    data = {}

    # Obtém as credenciais do inversor Solis
    credencial = CredencialInversor.objects.filter(
        inversor__name='solis'
    ).first()

    # Preenche o dicionário de dados com informações necessárias
    data['empresa_id'] = credencial.empresa_id
    data['username'], data['password'] = credencial.usuario, credencial.senha
    data['api_url'] = 'https://www.soliscloud.com:15555'
    data['tz'] = pytz.timezone('America/Sao_Paulo')

    # Realiza o login na plataforma Solis
    login_solis(data)

    # Atualiza informações dos clientes Solis
    atualiza_clientes_solis(data)

    # Obtém a lista de clientes Solis
    data['clientes'] = Cliente.objects.filter(inverter__name='solis')

    # Atualiza a geração diária para os clientes Solis
    atualiza_geracao_solis(data)


@util.close_old_connections
def busca_dados_rge():
    """
    Realiza a busca de dados da concessionária RGE para todos os clientes associados às credenciais.

    Esta função percorre as credenciais associadas à concessionária RGE, verifica se é necessário realizar
    uma nova leitura de dados para cada cliente e, se necessário, chama a função `busca_rge` com tentativas
    de retry em caso de falha.

    Nota: 
        A função utiliza o decorator `@util.close_old_connections` para garantir que conexões antigas com o banco de dados
        sejam fechadas antes de executar o código.

    Args:
        Nenhum.

    Raises:
        Nenhum.

    """
    credenciais = CredencialConcessionaria.objects.filter(
        concessionaria__nome='RGE'
    )

    # Obtenha o datetime atual no fuso horário 'America/Sao_Paulo'
    now = dt.now(pytz.timezone('America/Sao_Paulo'))

    # Loop através das credenciais e recupera os dados
    for credencial in credenciais:
        cliente_info = ClienteInfo.objects.get(cliente=credencial.cliente)
        proxima_leitura = cliente_info.proxima_leitura_concessionaria

        # Verifica se é necessário realizar uma nova leitura de dados para o cliente
        if proxima_leitura is None or proxima_leitura < now:

            @retry(
                stop=stop_after_attempt(3), wait=wait_fixed(60)
            )  # Espere 60 segundos entre as tentativas
            def busca_rge_with_retry(credencial, cliente_info):
                busca_rge(credencial, cliente_info)

            # Chama a função `busca_rge` com tentativas de retry em caso de falha
            busca_rge_with_retry(credencial, cliente_info)


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    Deleta entradas de execução de tarefas do APScheduler mais antigas que `max_age` do banco de dados.
    Isso ajuda a evitar que o banco de dados seja preenchido com registros históricos antigos que não são mais úteis.

    Args:
        max_age (int): O tempo máximo para reter registros históricos de execução de tarefas.
                       O padrão é 7 dias.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    """
    Comando de gerenciamento do Django para executar o APScheduler.

    Este comando inicializa e inicia o APScheduler, adicionando trabalhos para diferentes funções.
    O scheduler é executado em segundo plano e aciona as funções especificadas em intervalos agendados.

    Uso:
        python manage.py runscheduler

    Args:
        BaseCommand: Classe BaseCommand do Django.

    Raises:
        KeyboardInterrupt: Exceção lançada quando o scheduler é interrompido manualmente pelo usuário.

    Exemplo:
        >>> python manage.py runscheduler
    """

    help = 'Executa o APScheduler.'

    def handle(self, *args, **options):
        """
        Manipula a execução do APScheduler.

        Este método inicializa o scheduler, adiciona trabalhos para várias funções e inicia o scheduler.
        Ele é executado indefinidamente até ser interrompido pelo usuário.

        Args:
            *args: Argumentos adicionais passados pela linha de comando.
            **options: Opções adicionais passadas pela linha de comando.

        Raises:
            KeyboardInterrupt: Exceção lançada quando o scheduler é interrompido manualmente pelo usuário.

        Returns:
            None
        """
        # Inicializa o scheduler
        scheduler = BackgroundScheduler(
            timezone=settings.TIME_ZONE, misfire_grace_time=None
        )
        scheduler.add_jobstore(DjangoJobStore(), 'default')

        # Obtenha a hora atual
        now = dt.now()
        diferenca = 6

        # Adiciona trabalhos para diferentes funções
        scheduler.add_job(
            growatt_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=now,
            id='growatt_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'growatt_hourly_generation'.")

        next_5_min = now# + timedelta(minutes=diferenca)

        scheduler.add_job(
            sungrow_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='sungrow_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'sungrow_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            abb_fimer_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='abb_fimer_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'abb_fimer_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            fronius_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='fronius_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'fronius_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            refusol_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='refusol_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'refusol_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            canadian_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='canadian_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'canadian_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            deye_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='deye_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'deye_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            ecosolys_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='ecosolys_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'ecosolys_hourly_generation'.")

        next_5_min += timedelta(minutes=diferenca)

        scheduler.add_job(
            solis_hourly_generation,
            # trigger=CronTrigger(hour=hourly_time),  # Every 1 hour
            'interval',
            hours=1,
            next_run_time=next_5_min,
            id='solis_hourly_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'solis_hourly_generation'.")

        # Calcule a próxima vez que será 2 da manhã
        next_2_am = now.replace(hour=2, minute=0, second=0)

        if now.hour >= 2:
            # Se já passou das 2 da manhã hoje, programe para as 2 da manhã de amanhã
            next_2_am += timedelta(days=1)

        scheduler.add_job(
            growatt_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='growatt_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'growatt_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            sungrow_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='sungrow_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'sungrow_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            abb_fimer_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='abb_fimer_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'abb_fimer_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            fronius_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='fronius_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'fronius_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            refusol_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='refusol_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'refusol_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            canadian_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='canadian_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'canadian_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            deye_day_generation,
            # trigger=CronTrigger(hour=hour, minute=minute),  # Every 1 hour
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='deye_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'deye_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            ecosolys_day_generation,
            # trigger=CronTrigger(hour=daily_hour, minute=daily_minute),
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='ecosolys_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'ecosolys_day_generation'.")

        # Adicione 5 minutos para a próxima tarefa
        next_2_am += timedelta(minutes=diferenca)

        scheduler.add_job(
            solis_day_generation,
            # trigger=CronTrigger(hour=hour, minute=minute),  # Every 1 hour
            'interval',
            hours=24,
            next_run_time=next_2_am,
            id='solis_day_generation',  # The `id` assigned to each job MUST be unique
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'solis_day_generation'.")

        # Calcule a próxima vez que será 2 da manhã
        next_23 = now.replace(hour=23, minute=0, second=0)

        if now.hour >= 23:
            # Se já passou das 20 hoje, programe para as 20 da amanhã
            next_23 += timedelta(days=1)

        scheduler.add_job(
            busca_dados_rge,
            'interval',
            hours=24,
            next_run_time=next_23,
            id='busca_dados_rge',
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'busca_dados_rge'.")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week='sat', hour='00', minute='30'),
            id='delete_old_job_executions',
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added weekly job: 'delete_old_job_executions'.")

        try:
            # Inicia o scheduler
            logger.info('Starting scheduler...')
            scheduler.start()
            while True:
                t.sleep(10)
        except KeyboardInterrupt:
            # Trata a interrupção manual pelo usuário
            logger.info('Stopping scheduler...')
            scheduler.shutdown()
            logger.info('Scheduler shut down successfully!')
