# Importe as configurações do Django para que o script seja executado corretamente
import os

import django

# Configura as variáveis de ambiente do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# executar com python -m core.insert_scripts.insert_credencial_inversores na pasta raiz seven-extension

# Importa o modelo de CredencialInversor
from apps.clientes.models import CredencialInversor, Empresa, Inversor
from django.db import transaction

# Lista de informações de credenciais para os inversores
credenciais = [
  ''' 
    Colocar toda credencial como ('Responsável', 'inversor', 'user', 'password'),
  '''
]

# Função para adicionar as credenciais de acesso aos inversores na base de dados
@transaction.atomic
def adicionar_credenciais():
    for empresa_nome, inversor_nome, usuario, senha in credenciais:
        try:
            empresa = Empresa.objects.get(nome=empresa_nome)
            inversor = Inversor.objects.get(name=inversor_nome)

            credencial = CredencialInversor(
                empresa=empresa,
                inversor=inversor,
                usuario=usuario,
                senha=senha,
            )
            credencial.save()
        except Empresa.DoesNotExist:
            print(
                f"Empresa '{empresa_nome}' não encontrada. A credencial não foi adicionada."
            )
        except Inversor.DoesNotExist:
            print(
                f"Inversor '{inversor_nome}' não encontrado. A credencial não foi adicionada."
            )


# Executa a função para adicionar as credenciais
if __name__ == '__main__':
    adicionar_credenciais()
    print('Credenciais adicionadas com sucesso!')
