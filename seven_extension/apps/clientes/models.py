import os

import environ
from django.contrib.auth.models import (
    AbstractUser,
    Group,
    Permission,
    UserManager,
)
from django.core.exceptions import ValidationError
from django.db import models
from dotenv import load_dotenv
from fernet_fields import EncryptedCharField

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Definindo a chave Fernet
FERNET_KEYS = os.getenv('FERNET_KEYS')

"""
Caso necessário devido à importação dos dados do banco de dados de produção, rodar o comando:

SELECT setval('django_migrations_id_seq', (SELECT MAX(id) FROM django_migrations));

ou

SELECT setval('auth_permission_id_seq', (SELECT MAX(id) FROM auth_permission));

ou qualquer outro problema com sequencias, alterando o nome da sequencia e a tabela

SELECT setval('clientes_geracao_id_seq', (SELECT MAX(id) FROM clientes_geracao));
"""


class Inversor(models.Model):
    """
    Representa um inversor.

    Attributes:
        name (str): O nome do inversor.
    """

    name = models.CharField(max_length=25)

    def __str__(self):
        """
        Retorna uma representação em string do inversor.

        Returns:
            str: A representação em string do inversor.
        """
        return self.name

    class Meta:
        app_label = 'clientes'


class Cliente(models.Model):
    """
    Representa um cliente de geração de energia.

    Attributes:
        inverter (Inversor): O inversor associado ao cliente.
        plant_id (str): O identificador único da planta do cliente.
        plant_name (str): O nome da planta do cliente.
        energy_today (float): A quantidade de energia gerada hoje pelo cliente.
        energy_total (float): A quantidade total de energia gerada pelo cliente.
        latitude (str): A latitude da localização do cliente.
        longitude (str): A longitude da localização do cliente.
        geracao_media_projeto (float): A geração média projetada do cliente (pode ser nulo).

    """    

    inverter = models.ForeignKey(Inversor, on_delete=models.CASCADE)
    plant_id = models.CharField(max_length=50)
    plant_name = models.CharField(max_length=100)
    energy_today = models.FloatField(default=0)
    energy_total = models.FloatField(default=0)
    latitude = models.CharField(max_length=25, default=0)
    longitude = models.CharField(max_length=25, default=0)
    geracao_media_projeto = models.FloatField(default=0, null=True)

    class Meta:
        unique_together = ('plant_id', 'plant_name')
        app_label = 'clientes'
        indexes = [
            models.Index(fields=['plant_id'], name='idx_cli_plant_id'),
            models.Index(fields=['plant_name'], name='idx_cli_plant_name'),
        ]

    def __str__(self):
        """
        Retorna uma representação em string do cliente.

        Returns:
            str: A representação em string do cliente.
        """
        return self.plant_name


class Geracao(models.Model):
    """
    Representa a geração de energia de um cliente.

    Attributes:
        cliente (Cliente): O cliente associado à geração de energia.
        timestamp (datetime): O timestamp da geração de energia.
        energystamp (float): A quantidade de energia gerada.
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    energystamp = models.FloatField(default=0)

    class Meta:
        unique_together = ('cliente', 'timestamp')
        app_label = 'clientes'
        indexes = [
            models.Index(fields=['timestamp'], name='idx_ger_timestamp'),
            models.Index(
                fields=['cliente', 'timestamp'], name='idx_ger_cli_time'
            ),
            models.Index(fields=['-timestamp'], name='idx_ger_Dtimestamp'),
        ]

    def __str__(self):
        """
        Retorna uma representação em string da geração total completa diária.

        Returns:
            str: A representação em string de todos os campos do modelo.
        """
        return f'{self.cliente} - {self.timestamp} - {self.energystamp}'


class GeracaoDiaria(models.Model):
    """
    Representa a geração diária de energia de um cliente.

    Attributes:
        cliente (Cliente): O cliente associado à geração de energia.
        timestamp (datetime): O timestamp da geração de energia.
        energystamp (float): A quantidade de energia gerada.
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    energystamp = models.FloatField(default=0)

    class Meta:
        unique_together = ('cliente', 'timestamp')
        app_label = 'clientes'
        indexes = [
            models.Index(fields=['-timestamp'], name='idx_gerdia_Dtimestamp'),
        ]

    def __str__(self):
        """
        Retorna uma representação em string da geração diária.

        Returns:
            str: A representação em string de todos os campos do modelo.
        """
        return f'{self.cliente} - {self.timestamp} - {self.energystamp}'


class Estado(models.Model):
    """
    Representa um estado.

    Attributes:
        uf (str): A sigla do estado.
        nome (str): O nome completo do estado.

    """

    uf = models.CharField(max_length=2)
    nome = models.CharField(max_length=255)

    def __str__(self):
        """
        Retorna uma representação em string do estado.

        Returns:
            str: A sigla do estado.
        """
        return self.uf

    class Meta:
        app_label = 'clientes'


class Empresa(models.Model):
    """
    Representa uma empresa.

    Attributes:
        nome (str): O nome da empresa.
        cnpj (str): O CNPJ único da empresa.
        estado (Estado): O estado associado à empresa.

    """

    nome = models.CharField(max_length=100)
    cnpj = models.CharField(max_length=14, unique=True)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, null=True)

    def __str__(self):
        """
        Retorna uma representação em string da empresa.

        Returns:
            str: A representação em string da empresa.
        """
        return self.nome

    class Meta:
        app_label = 'clientes'


class CredencialInversor(models.Model):
    """
    Representa uma credencial de acesso a um inversor para uma empresa.

    Attributes:
        empresa (Empresa): A empresa associada à credencial.
        inversor (Inversor): O inversor associado à credencial.
        usuario (EncryptedCharField): O usuário do inversor criptografado para a empresa.
        senha (EncryptedCharField): A senha do inversor criptografado para a empresa.
    """

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, null=True, blank=True
    )
    inversor = models.ForeignKey(Inversor, on_delete=models.CASCADE)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, null=True, blank=True
    )
    usuario = EncryptedCharField(max_length=25)
    senha = EncryptedCharField(max_length=25)

    class Meta:
        app_label = 'clientes'

    def __str__(self):
        """
        Retorna uma representação em string da credencial.

        Returns:
            str: A representação em string da credencial.
        """
        return (
            f'{self.empresa} - {self.inversor} - {self.usuario} - {self.senha}'
        )


class Concessionaria(models.Model):
    """
    Representa uma concessionária.

    Attributes:
        nome (str): O nome da concessionária.
        estado (Estado): O estado associado à concessionária.

    """

    nome = models.CharField(max_length=100, unique=True)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, null=True)

    def __str__(self):
        """
        Retorna uma representação em string da concessionária.

        Returns:
            str: O nome da concessionária.
        """
        return self.nome

    class Meta:
        app_label = 'clientes'


class CredencialConcessionaria(models.Model):
    """
    Representa as credenciais de uma concessionária associadas a um cliente.

    Attributes:
        concessionaria (Concessionaria): A concessionária associada às credenciais.
        cliente (Cliente): O cliente associado às credenciais.
        usuario (str): O nome de usuário para autenticação.
        senha (str): A senha para autenticação.
        cpf_cnpj (str, optional): O CPF ou CNPJ associado às credenciais (opcional).

    """

    concessionaria = models.ForeignKey(
        Concessionaria, on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    usuario = EncryptedCharField(max_length=40)
    senha = EncryptedCharField(max_length=25)
    cpf_cnpj = EncryptedCharField(max_length=14, null=True, blank=True)
    fone = models.CharField(max_length=11, null=True, blank=True)

    def __str__(self):
        """
        Retorna uma representação em string das credenciais.

        Returns:
            str: Uma representação em string contendo o nome da concessionária, nome de usuário e senha.
        """
        return f'{self.concessionaria} - {self.usuario} {self.senha}'

    class Meta:
        app_label = 'clientes'
        unique_together = ('concessionaria', 'cliente')


class Instalacao(models.Model):
    """
    Representa uma instalação associada a um cliente.

    Attributes:
        cliente (Cliente): O cliente associado à instalação.
        codigo (str): O código único da instalação.
        endereco (str, optional): O endereço da instalação (opcional).

    """

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=25)
    endereco = models.CharField(max_length=100, default='')

    def __str__(self):
        """
        Retorna uma representação em string da instalação.

        Returns:
            str: Uma representação em string contendo o nome do cliente, código e endereço da instalação.
        """
        cliente_str = str(self.cliente)
        codigo_str = str(self.codigo)
        endereco_str = str(self.endereco)
        return f'{cliente_str} - {codigo_str} - {endereco_str}'

    class Meta:
        app_label = 'clientes'
        unique_together = ('cliente', 'codigo')


class Consumo(models.Model):
    """
    Representa o consumo de energia associado a uma instalação em um determinado período.

    Attributes:
        instalacao (Instalacao): A instalação associada ao consumo.
        consumo (float): A quantidade de energia consumida.
        mes_ano (datetime): O timestamp representando o mês e ano do consumo.
        valor (float): O valor total associado ao consumo.
        tarifa (float, optional): A tarifa de energia (opcional).

    """

    instalacao = models.ForeignKey(
        Instalacao, on_delete=models.CASCADE, db_index=True
    )
    consumo = models.FloatField(default=0)
    mes_ano = models.DateTimeField(null=False, db_index=True)
    valor = models.FloatField(default=0)
    tarifa = models.FloatField(default=0, null=True)

    def __str__(self):
        """
        Retorna uma representação em string do consumo.

        Returns:
            str: Uma representação em string contendo a instalação, consumo, mês/ano, valor e tarifa.
        """
        return f'{self.instalacao} - {self.consumo} - {self.mes_ano} - {self.valor} - {self.tarifa}'

    class Meta:
        app_label = 'clientes'
        unique_together = ('instalacao', 'mes_ano')


class Injecao(models.Model):
    """
    Representa a injeção de energia associada a uma instalação em um determinado período.

    Attributes:
        instalacao (Instalacao): A instalação associada à injeção.
        tipo_geracao (str, optional): O tipo de geração de energia (opcional).
        tipo_instalacao (str, optional): O tipo de instalação (opcional).
        mes_referencia (datetime): O timestamp representando o mês de referência.
        data_leitura_anterior (datetime, optional): O timestamp da leitura anterior (opcional).
        porcentagem (float): A porcentagem associada à injeção de energia.
        consumo_mensal_ponta (float): O consumo mensal em horário de ponta.
        consumo_mensal_fora_ponta (float): O consumo mensal fora do horário de ponta.
        energia_injetada_ponta (float): A quantidade de energia injetada em horário de ponta.
        energia_injetada_fora_ponta (float): A quantidade de energia injetada fora do horário de ponta.
        energia_recebida_ponta (float): A quantidade de energia recebida em horário de ponta.
        energia_recebida_fora_ponta (float): A quantidade de energia recebida fora do horário de ponta.
        creditos_utilizados_ponta (float): Os créditos utilizados em horário de ponta.
        creditos_utilizados_fora_ponta (float): Os créditos utilizados fora do horário de ponta.
        creditos_expirados_ponta (float): Os créditos expirados em horário de ponta.
        creditos_expirados_fora_ponta (float): Os créditos expirados fora do horário de ponta.
        saldo_mensal_ponta (float): O saldo mensal em horário de ponta.
        saldo_mensal_fora_ponta (float): O saldo mensal fora do horário de ponta.
        creditos_expirar_ponta (float): Os créditos a expirar em horário de ponta.
        creditos_expirar_fora_ponta (float): Os créditos a expirar fora do horário de ponta.
        mes_expiracao (datetime, optional): O timestamp do mês de expiração (opcional).
        saldo_acumulado (float, optional): O saldo acumulado (opcional).

    """

    instalacao = models.ForeignKey(Instalacao, on_delete=models.CASCADE)
    tipo_geracao = models.CharField(max_length=100, null=True)
    tipo_instalacao = models.CharField(max_length=50, null=True)
    mes_referencia = models.DateTimeField(null=False)
    data_leitura_anterior = models.DateTimeField(null=True)
    porcentagem = models.FloatField()
    consumo_mensal_ponta = models.FloatField()
    consumo_mensal_fora_ponta = models.FloatField()
    energia_injetada_ponta = models.FloatField()
    energia_injetada_fora_ponta = models.FloatField()
    energia_recebida_ponta = models.FloatField()
    energia_recebida_fora_ponta = models.FloatField()
    creditos_utilizados_ponta = models.FloatField()
    creditos_utilizados_fora_ponta = models.FloatField()
    creditos_expirados_ponta = models.FloatField()
    creditos_expirados_fora_ponta = models.FloatField()
    saldo_mensal_ponta = models.FloatField()
    saldo_mensal_fora_ponta = models.FloatField()
    creditos_expirar_ponta = models.FloatField()
    creditos_expirar_fora_ponta = models.FloatField()
    mes_expiracao = models.DateTimeField(null=True)
    saldo_acumulado = models.FloatField(null=True)

    def __str__(self):
        """
        Retorna uma representação em string da injeção de energia.

        Returns:
            str: Uma representação em string contendo a instalação, energia injetada fora do horário de ponta,
            tipo de geração, tipo de instalação e mês de referência.
        """
        return f'{self.instalacao} - {self.energia_injetada_fora_ponta} - {self.tipo_geracao} - {self.tipo_instalacao} - {self.mes_referencia}'

    class Meta:
        app_label = 'clientes'
        unique_together = ('instalacao', 'mes_referencia')



class TipoUsuario(models.Model):
    """
    Representa um tipo de usuário.

    Attributes:
        nome_tipo (str): O nome do tipo de usuário.

    """

    nome_tipo = models.CharField(max_length=50, unique=True)

    def __str__(self):
        """
        Retorna uma representação em string do tipo de usuário.

        Returns:
            str: O nome do tipo de usuário.
        """
        return self.nome_tipo

    class Meta:
        app_label = 'clientes'


class UsuarioCustomizadoManager(UserManager):
    """
    Gerenciador personalizado para a classe de usuário customizado.

    Este gerenciador estende o UserManager padrão do Django, adicionando
    funcionalidades específicas para criar um superusuário com um tipo de
    usuário predefinido.

    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """
        Cria e retorna um superusuário com o tipo de usuário predefinido.

        Args:
            username (str): Nome de usuário do superusuário.
            email (str, optional): Endereço de e-mail do superusuário (opcional).
            password (str, optional): Senha do superusuário (opcional).
            **extra_fields: Outros campos adicionais a serem definidos.

        Returns:
            UsuarioCustomizado: O superusuário criado.

        """
        DEFAULT_TIPO_USUARIO = TipoUsuario.objects.get(nome_tipo='admin')
        extra_fields.setdefault('tipo_usuario', DEFAULT_TIPO_USUARIO)
        return super().create_superuser(username, email, password, **extra_fields)



class UsuarioCustomizado(AbstractUser):
    """
    Classe personalizada de usuário que herda do AbstractUser.

    Campos herdados:
    - username: Nome de usuário. Usado para autenticação.
    - first_name: Primeiro nome do usuário.
    - last_name: Sobrenome do usuário.
    - email: Endereço de email do usuário. Usado para autenticação.
    - password: Senha do usuário, armazenada de forma segura (hash).
    - date_joined: Data de adesão do usuário.
    - last_login: Data do último login do usuário.
    - is_active: Um campo booleano que indica se a conta do usuário está ativa.
    - is_staff: Um campo booleano que indica se o usuário tem acesso à interface administrativa.
    - is_superuser: Um campo booleano que indica se o usuário tem todos os privilégios.
    - groups: Relação com grupos.
    - user_permissions: Relação com permissões.
    - tipo_usuario: Campo personalizado para definir o tipo de usuário.
    - cliente: Relação com o modelo Cliente.
    - empresa: Relação com o modelo Empresa.
    - objects: Gerenciador personalizado para a classe UsuarioCustomizado.

    """

    email = models.EmailField(unique=True)
    tipo_usuario = models.ForeignKey(TipoUsuario, on_delete=models.CASCADE)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, null=True, blank=True
    )  # Permitir nulo para administradores e integradores
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, default=1, null=True, blank=True
    )   # Permitir nulo para administradores
    groups = models.ManyToManyField(
        Group, related_name='custom_user_set', blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission, related_name='custom_user_set', blank=True
    )
    objects = UsuarioCustomizadoManager()

    class Meta:
        app_label = 'clientes'

    def clean(self):
        """
        Executa verificações de validação personalizadas durante o processo de limpeza.

        Raises:
            ValidationError: Se as condições de validação não forem atendidas.
        """
        # Adicione esta verificação para garantir que o tipo_usuario exista antes de tentar acessá-lo
        if hasattr(self, 'tipo_usuario'):
            # Se o tipo_usuario for 'cliente', então 'cliente' não pode ser nulo
            if (
                self.tipo_usuario.nome_tipo == 'cliente'
                and self.cliente is None
            ):
                raise ValidationError(
                    "Os usuários do tipo 'cliente' devem estar associados a um cliente."
                )
            if self.tipo_usuario.nome_tipo == 'cliente' and self.empresa:
                raise ValidationError(
                    "Os usuários do tipo 'cliente' não devem estar associados a uma empresa nessa tabela."
                )
            if (
                self.tipo_usuario.nome_tipo == 'integrador'
                and self.cliente is not None
            ):
                raise ValidationError(
                    "Os usuários do tipo 'integrador' não podem estar associados a um cliente."
                )
            if self.tipo_usuario.nome_tipo == 'admin' and (
                self.cliente or self.empresa
            ):
                raise ValidationError(
                    "Os usuários do tipo 'admin' não podem estar associados a um cliente ou empresa."
                )



class RelacaoClienteEmpresa(models.Model):
    """
    Representa a relação entre um cliente e uma empresa.

    Attributes:
        cliente (Cliente): O cliente associado à relação.
        empresa (Empresa): A empresa associada à relação.

    """

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)

    def __str__(self):
        """
        Retorna uma representação em string da relação cliente-empresa.

        Returns:
            str: Uma representação em string contendo o nome da planta do cliente e o nome da empresa.
        """
        return f'{self.cliente.plant_name} - {self.empresa.nome}'

    class Meta:
        app_label = 'clientes'
        unique_together = ('cliente', 'empresa')


class Notificacao(models.Model):
    """
    Representa uma notificação.

    Attributes:
        inicio_notificacao (datetime): O timestamp de início da notificação (automático ao criar).
        final_notificacao (datetime, optional): O timestamp de término da notificação (opcional).
        estilo_notificacao (str): O estilo da notificação (aviso, erro, sucesso).
        local_notificacao (str): O local da notificação (geral, notificação).
        abrangencia_notificacao (str, optional): A abrangência da notificação (empresa, clientes, todos) (opcional).
        mensagem (str): O texto da notificação.
        tipo_usuario (TipoUsuario, optional): O tipo de usuário associado à notificação (opcional).
        inversor (Inversor, optional): O inversor associado à notificação (opcional).
        cliente (Cliente, optional): O cliente associado à notificação (opcional).
        empresa (Empresa, optional): A empresa associada à notificação (opcional).

    """

    ESTILO_NOTIFICACAO_CHOICES = [
        ('aviso', 'Aviso'),
        ('erro', 'Erro'),
        ('sucesso', 'Sucesso'),
    ]

    LOCAL_NOTIFICACAO_CHOICES = [
        ('geral', 'Geral'),
        ('notificacao', 'Notificação'),
    ]

    ABRANGENCIA_CHOICES = [
        ('empresa', 'Empresa'),
        ('clientes', 'Clientes'),
        ('todos', 'Todos'),
    ]

    inicio_notificacao = models.DateTimeField(auto_now_add=True)
    final_notificacao = models.DateTimeField(null=True, blank=True)
    estilo_notificacao = models.CharField(
        max_length=10, choices=ESTILO_NOTIFICACAO_CHOICES
    )
    local_notificacao = models.CharField(
        max_length=12, choices=LOCAL_NOTIFICACAO_CHOICES
    )
    abrangencia_notificacao = models.CharField(
        max_length=8, choices=ABRANGENCIA_CHOICES, null=True, blank=True
    )
    mensagem = models.TextField()
    tipo_usuario = models.ForeignKey(
        TipoUsuario, on_delete=models.CASCADE, null=True, blank=True
    )
    inversor = models.ForeignKey(
        Inversor, on_delete=models.CASCADE, null=True, blank=True
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, null=True, blank=True
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        """
        Retorna uma representação em string da notificação.

        Returns:
            str: Uma representação em string contendo estilo, local, tipo de usuário e mensagem.
        """
        return f'{self.estilo_notificacao} - {self.local_notificacao} - {self.tipo_usuario} - {self.mensagem}'

    class Meta:
        app_label = 'clientes'


class ClienteInfo(models.Model):
    """
    Representa informações adicionais associadas a um cliente.

    Attributes:
        cliente (Cliente): O cliente associado às informações.
        ultima_geracao (datetime, optional): O timestamp da última geração de energia (opcional).
        ultima_geracao_diaria (datetime, optional): O timestamp da última geração diária de energia (opcional).
        proxima_leitura_concessionaria (datetime, optional): O timestamp da próxima leitura da concessionária (opcional).

    """

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE)
    ultima_geracao = models.DateTimeField(null=True, blank=True)
    ultima_geracao_diaria = models.DateTimeField(null=True, blank=True)
    proxima_leitura_concessionaria = models.DateTimeField(
        null=True, blank=True
    )

    def __str__(self):
        """
        Retorna uma representação em string das informações do cliente.

        Returns:
            str: Uma representação em string contendo o cliente, última geração, última geração diária
                 e próxima leitura da concessionária.
        """
        return f'{self.cliente} - {self.ultima_geracao} - {self.ultima_geracao_diaria} - {self.proxima_leitura_concessionaria}'

    class Meta:
        app_label = 'clientes'
