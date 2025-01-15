# Importe as configurações do Django para que o script seja executado corretamente
import os

import django

# Configura as variáveis de ambiente do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# executar com python -m core.insert_scripts.insert_tipo_usuario na pasta raiz seven-extension

# Importa o modelo de Inversor
from apps.clientes.models import TipoUsuario

# Lista dos nomes dos tipos de usuarios
tipo_usuario = [
    'admin',
    'integrador',
    'cliente',
]

# Função para adicionar os tipos de usuarios na base de dados
def adicionar_tipo_usuario():
    for nome in tipo_usuario:
        tipo = TipoUsuario(nome_tipo=nome)
        tipo.save()


# Executa a função para adicionar os tipos de usuarios
if __name__ == '__main__':
    adicionar_tipo_usuario()
    print('Tipos de Usuários adicionados com sucesso!')
