"""
Arquivo de testes para as funções do módulo 'get_inversor_energy'.

Este arquivo utiliza a biblioteca Ward para a execução dos testes.
"""

import os
import django

# Configurações iniciais do Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
django.setup()

from ward import test
from apps.clientes.jobs.get_inversor_energy import convert_energy_units, hash_password

@test("Teste para verificar se a conversão de kWh para Wh está correta")
def _():
    result = convert_energy_units('10.5 kWh')
    assert isinstance(result, float)
    assert result == 10_500
    
@test("Teste para verificar se a conversão de mWh para Wh está correta")
def _():
    result = convert_energy_units('1.5 mWh')
    assert isinstance(result, float)
    assert result == 1_500_000
    
@test("Teste para verificar se o valor retornará caso seja enviado sem números")
def _():
    result = convert_energy_units('a')
    assert result is not None
    
@test("Teste para verificar se o valor retornará caso não tenha a unidade de medida")
def _():
    result = convert_energy_units(0)
    assert result is not None    
    
@test("Teste para verificar se será retornado o valor correto caso não tenha uma unidade de medida e tenha '.' ")
def _():
    result = convert_energy_units(900.0)
    assert result == 900.0 
    
@test("Teste para verificar se será retornado o valor correto caso não tenha uma unidade de medida e não tenha '.' ")
def _():
    result = convert_energy_units(900)
    assert result == 900
    
@test("Teste para verificar se o valor retornará caso as letras tenham tamanhos diferentes")
def _():
    result = convert_energy_units('10.5 kwh')
    assert isinstance(result, float)
    assert result == 10_500
    
@test("Teste para verificar se o valor retornará caso seja enviada uma vírgula ao invés de ponto")
def _():
    result = convert_energy_units('10,5 mwh')
    assert isinstance(result, float)
    assert result == 10_500_000

@test("Teste para verificar a codificação correta da senha para inversores canadian")
def _():
    result = hash_password('123456')
    assert result == '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92'
    
@test("Teste para verificar se o inversor ecosolys tem o valor de energia salvo corretamente")
def _():
    result = convert_energy_units('8.051 kwh')
    assert result == 8_051
    
@test("Teste para verificar se a conversão de wh com ponto funciona")
def _():
    result = convert_energy_units('2.761 Wh')
    assert result == 2_761
    
@test("Teste para verificar se a conversão de wh sem ponto funciona")
def _():
    result = convert_energy_units('761 Wh')
    assert result == 761
    
@test("Teste para verificar se a conversão de wh sem ponto e mais de mil funciona")
def _():
    result = convert_energy_units('2761 Wh')
    assert result == 2_761
