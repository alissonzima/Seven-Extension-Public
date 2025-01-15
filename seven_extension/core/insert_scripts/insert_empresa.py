# Importe as configurações do Django para que o script seja executado corretamente
import os

import django

# Configura as variáveis de ambiente do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# executar com python -m core.insert_scripts.insert_empresa na pasta raiz seven-extension

# Importa o modelo de Empresa e Estado
from apps.clientes.models import Empresa, Estado
from django.db import transaction

# Lista de informações das empresas
empresas = [
    ('put_empresa', 'put_cnpj', 'put_uf'),
    # Adicione outras empresas aqui
]

# Função para adicionar empresas na base de dados
@transaction.atomic
def adicionar_empresas():
    for nome, cnpj, uf in empresas:
        try:
            estado = Estado.objects.get(uf=uf)

            empresa = Empresa(nome=nome, cnpj=cnpj, estado=estado)
            empresa.save()
        except Estado.DoesNotExist:
            print(
                f"Estado '{uf}' não encontrado. A empresa '{nome}' não foi adicionada."
            )


# Executa a função para adicionar empresas
if __name__ == '__main__':
    adicionar_empresas()
    print('Empresas adicionadas com sucesso!')
