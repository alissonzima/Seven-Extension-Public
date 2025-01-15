# Importe as configurações do Django para que o script seja executado corretamente
import os

import django

# Configura as variáveis de ambiente do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# executar com python -m core.insert_scripts.insert_inversores na pasta raiz seven-extension

# Importa o modelo de Inversor
from apps.clientes.models import Inversor

# Lista dos nomes dos inversores
inversores = [
    'growatt',
    'sungrow',
    'goodwe',
    'abb_fimer',
    'fronius',
    'refusol',
    'canadian',
    'deye',
    'ecosolys',
    'solis',
]

# Função para adicionar os inversores na base de dados
def adicionar_inversores():
    for nome in inversores:
        inversor = Inversor(name=nome)
        inversor.save()


# Executa a função para adicionar os inversores
if __name__ == '__main__':
    adicionar_inversores()
    print('Inversores adicionados com sucesso!')
