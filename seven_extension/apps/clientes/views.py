import json
import locale
from datetime import datetime as dt

import folium
from apps.clientes.app_geracao_clientes import *
from apps.clientes.forms import (
    AtualizarSenhaForm,
    CredencialConcessionariaForm,
    CredencialInversorForm,
    CriarUsuarioCustomizadoForm,
    UsuarioCustomizadoForm,
)
from apps.clientes.jobs.get_concessionaria_data import busca_rge
from apps.clientes.jobs.get_inversor_energy import is_number
from apps.clientes.methods import get_context_data, printl
from apps.clientes.models import (
    Cliente,
    ClienteInfo,
    Consumo,
    CredencialConcessionaria,
    CredencialInversor,
    Empresa,
    Injecao,
    Instalacao,
    Inversor,
    Notificacao,
    RelacaoClienteEmpresa,
    TipoUsuario,
)
from core.custom_exceptions import CPFouCNPJNaoEncontradoError, TelNaoEncontradoError
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

def datetime_serializer(obj):
    """
    Serializa objetos do tipo datetime para o formato ISO 8601 para JSON.

    Args:
        obj: O objeto a ser serializado.

    Returns:
        str: Representação ISO 8601 do objeto datetime.

    Raises:
        TypeError: Se o objeto não for do tipo datetime.

    Notas:
        - Esta função é usada como parte do processo de serialização JSON.
        - Converte objetos datetime para suas representações ISO 8601.
        - Útil ao lidar com a serialização JSON de objetos que contêm datetime.

    Exemplo:
        data = {'timestamp': datetime.datetime.now()}
        json_data = json.dumps(data, default=datetime_serializer)
    """
    if isinstance(obj, dt):
        return obj.isoformat()
    raise TypeError(
        f'Objeto do tipo {obj.__class__.__name__} não é serializável para JSON.'
    )


def notificacao(request):
    """
    Exibe a página de notificações e processa formulários de criação de notificações.

    Args:
        request: Objeto HttpRequest contendo detalhes sobre a solicitação.

    Returns:
        HttpResponse: Resposta HTTP renderizada.

    Notas:
        - A função processa o formulário de criação de notificações quando um POST é recebido.
        - Requer que o usuário seja um administrador para acessar a página e criar notificações.
        - Usa a função get_context_data para obter dados do contexto.

    """
    context = get_context_data(request)

    # Verifica se o usuário é um administrador, caso contrário, retorna uma página de erro 403
    if context['user_type'] != 'admin':
        return render(request, 'home/page-403.html', status=403)

    context['segment'] = 'notificacao'

    # Obtém listas de empresas, clientes e inversores para preencher opções nos formulários
    empresas = Empresa.objects.all().order_by('nome')
    clientes = Cliente.objects.all().order_by('plant_name')
    inversores = Inversor.objects.all().order_by('name')

    context['empresas'] = empresas
    context['clientes'] = clientes
    context['inversores'] = inversores
    context[
        'estilo_notificacao_choices'
    ] = Notificacao.ESTILO_NOTIFICACAO_CHOICES
    context[
        'local_notificacao_choices'
    ] = Notificacao.LOCAL_NOTIFICACAO_CHOICES

    # Processa o formulário quando um POST é recebido
    if request.method == 'POST':
        estilo_notificacao = request.POST.get('estilo_notificacao')
        printl(estilo_notificacao)
        local_notificacao = request.POST.get('local_notificacao')
        printl(local_notificacao)
        mensagem = request.POST.get('mensagem')
        printl(mensagem)
        final_notificacao = request.POST.get('final_notificacao')
        printl(final_notificacao)
        seletor = request.POST.get('seletor')
        printl(seletor)

        # Cria uma instância de Notificacao com base nos dados do formulário
        notificacao = Notificacao(
            estilo_notificacao=estilo_notificacao,
            local_notificacao=local_notificacao,
            mensagem=mensagem,
            final_notificacao=final_notificacao if final_notificacao else None,
        )

        # Configura a abrangência da notificação com base no seletor do formulário
        if seletor == 'todos':
            notificacao.abrangencia_notificacao = 'todos'
        elif seletor == 'integradores':
            notificacao.abrangencia_notificacao = 'empresa'
            notificacao.tipo_usuario = TipoUsuario.objects.get(
                nome_tipo='integrador'
            )
        elif seletor == 'integradorX':
            notificacao.abrangencia_notificacao = 'empresa'
            notificacao.tipo_usuario = TipoUsuario.objects.get(
                nome_tipo='integrador'
            )
            notificacao.empresa_id = request.POST.get('empresa')
        elif seletor == 'clienteX':
            notificacao.abrangencia_notificacao = 'clientes'
            notificacao.tipo_usuario = TipoUsuario.objects.get(
                nome_tipo='cliente'
            )
            notificacao.cliente_id = request.POST.get('cliente')
        elif seletor == 'clientesIntegradorX':
            notificacao.abrangencia_notificacao = 'clientes'
            notificacao.empresa_id = request.POST.get('empresa')
        elif seletor == 'clientesInversorX':
            notificacao.abrangencia_notificacao = 'clientes'
            notificacao.inversor_id = request.POST.get('inversor')

        # Salva a notificação no banco de dados
        notificacao.save()
        messages.success(request, 'Notificação ativada com sucesso')

    # Renderiza a página de notificação com o contexto
    return render(request, 'clientes/notificacao.html', context=context)


@login_required
def profile_user(request):
    """
    Exibe o perfil do usuário, permitindo a edição de informações do usuário, concessionária, inversor e senha.

    Args:
        request: Objeto HttpRequest contendo detalhes sobre a solicitação.

    Returns:
        HttpResponse: Resposta HTTP renderizada.

    Notas:
        - Requer autenticação do usuário.
        - Permite ao usuário editar informações do usuário, concessionária, inversor e senha.
        - A função processa formulários quando um POST é recebido.
        - Usa a função get_context_data para obter dados do contexto.

    """

    context = get_context_data(request)

    context['segment'] = 'profile_user'

    (
        form_usuario,
        form_credencial_concessionaria,
        form_credencial_inversor,
        form_senha,
        form_criar_usuario,
    ) = (None, None, None, None, None)

    # Processa o formulário quando um POST é recebido
    if request.method == 'POST':

        # Obtém o ID do cliente a partir do formulário ou do usuário autenticado
        if request.user.cliente:
            cliente_id = request.user.cliente.id
        else:
            cliente_id = request.POST.get('client_form_id')

        if cliente_id == 'None':
            cliente_id = None

        form_selecionado = request.POST.get('form-selecionado')

        # Processa o formulário com base na opção selecionada
        if form_selecionado == 'usuario':
            if cliente_id:
                try:
                    usuario = UsuarioCustomizado.objects.get(
                        cliente_id=cliente_id
                    )
                except UsuarioCustomizado.DoesNotExist:
                    usuario = None
            else:
                usuario = UsuarioCustomizado.objects.get(id=request.user_id)

        if 'buscar-dados-rge' in request.POST:
            try:
                credencial = CredencialConcessionaria.objects.get(
                    cliente_id=cliente_id
                )
                cliente_info = ClienteInfo.objects.get(
                    cliente=credencial.cliente
                )
                busca_rge(credencial, cliente_info)
                messages.success(
                    request, 'Dados da concessionária atualizados com sucesso'
                )
            except CPFouCNPJNaoEncontradoError as e:
                messages.error(
                    request, str(e)
                )  # Exibe a mensagem personalizada
            except TelNaoEncontradoError as e:
                messages.error(
                    request, str(e)
                )  # Exibe a mensagem personalizada
            except Exception as e:
                #print('Erro na busca:', str(e))
                messages.error(
                    request,
                    'Problema encontrado com a busca de dados. Um aviso foi enviado ao administrador: ' + str(e),
                )

        elif form_selecionado == 'criar-usuario':
            form_criar_usuario = CriarUsuarioCustomizadoForm(request.POST)
            if form_criar_usuario.is_valid():
                usuario_customizado = form_criar_usuario.save(commit=False)
                usuario_customizado.cliente = Cliente.objects.get(
                    id=cliente_id
                )
                usuario_customizado.tipo_usuario = TipoUsuario.objects.get(
                    nome_tipo='cliente'
                )
                # Salve o objeto no banco de dados
                usuario_customizado.save()
                usuario = UsuarioCustomizado.objects.get(cliente_id=cliente_id)

        elif form_selecionado == 'usuario':
            form_usuario = UsuarioCustomizadoForm(
                request.POST, instance=usuario
            )
            printl(form_usuario.errors)
            if form_usuario.is_valid():

                usuario_form = form_usuario.save(commit=False)
                usuario_form.save(update_fields=['first_name', 'last_name'])
                messages.success(
                    request, 'Dados do usuário atualizados com sucesso'
                )

        elif form_selecionado == 'concessionaria':
            try:
                credencial_concessionaria = (
                    CredencialConcessionaria.objects.get(cliente_id=cliente_id)
                )
                form_credencial_concessionaria = CredencialConcessionariaForm(
                    request.POST,
                    instance=credencial_concessionaria,
                    user_type=request.user_type,
                )
                # print(form_credencial_concessionaria.errors)

                if form_credencial_concessionaria.is_valid():
                    concessionaria_form = form_credencial_concessionaria.save(
                        commit=False
                    )
                    concessionaria_form.save(
                        update_fields=[
                            'concessionaria',
                            'usuario',
                            'senha',
                            'cpf_cnpj',
                        ]
                    )
                    # Acesse o valor do campo consumo_do_projeto
                    geracao_projeto = (
                        form_credencial_concessionaria.cleaned_data[
                            'geracao_projeto'
                        ]
                    )
                    # Salve o valor do consumo_do_projeto na model Cliente
                    cliente = Cliente.objects.get(id=cliente_id)

                    if geracao_projeto != '' and is_number(geracao_projeto):
                        cliente.geracao_media_projeto = geracao_projeto
                    else:
                        cliente.geracao_media_projeto = None

                    cliente.save()
                    messages.success(
                        request,
                        'Dados da concessionária atualizados com sucesso',
                    )

            except CredencialConcessionaria.DoesNotExist:
                form_credencial_concessionaria = CredencialConcessionariaForm(
                    request.POST, user_type=request.user_type
                )
                if form_credencial_concessionaria.is_valid():
                    concessionaria_form = form_credencial_concessionaria.save(
                        commit=False
                    )
                    concessionaria_form.cliente_id = cliente_id
                    concessionaria_form.save()
                    # Acesse o valor do campo consumo_do_projeto
                    geracao_projeto = (
                        form_credencial_concessionaria.cleaned_data[
                            'geracao_projeto'
                        ]
                    )
                    # Salve o valor do consumo_do_projeto na model Cliente
                    cliente = Cliente.objects.get(id=cliente_id)

                    if geracao_projeto != '' and is_number(geracao_projeto):
                        cliente.geracao_media_projeto = geracao_projeto
                    else:
                        cliente.geracao_media_projeto = None

                    cliente.save()
                    messages.success(
                        request, 'Dados da concessionária salvos com sucesso'
                    )

        elif form_selecionado == 'inversor':
            form_credencial_inversor = CredencialInversorForm(request.POST)
            if form_credencial_inversor.is_valid():
                credencial_inversor = form_credencial_inversor.save(
                    commit=False
                )
                if request.user_empresa:
                    credencial_inversor.empresa_id = request.user_empresa
                else:
                    credencial_inversor.cliente_id = cliente_id
                credencial_inversor.save()
                messages.success(
                    request, 'Dados do inversor salvos com sucesso'
                )

        elif form_selecionado == 'senha':
            form_senha = AtualizarSenhaForm(request.user, request.POST)
            printl(form_senha.errors)

            if form_senha.is_valid():
                form_senha.save()
                messages.success(request, 'Senha alterada com sucesso')

    # Obtém informações adicionais para o contexto
    if request.user.cliente:
        context['client_id'] = request.user.cliente.id
    elif request.GET.get('cliente'):
        context['client_id'] = request.GET.get('cliente')
    elif request.POST.get('client_form_id'):
        context['client_id'] = request.POST.get('client_form_id')
    else:
        context['client_id'] = None

    if context['client_id'] == 'None':
        context['client_id'] = None

    # Adiciona informações do cliente ao contexto
    if context['client_id']:
        cliente = Cliente.objects.get(id=context['client_id'])
        context['cliente_plant_name'] = cliente.plant_name
        # context['nome_cliente'] = cliente.plant_name
        try:
            usuario = UsuarioCustomizado.objects.get(cliente=cliente)
        except UsuarioCustomizado.DoesNotExist:
            usuario = None
    else:
        cliente = None
        usuario = UsuarioCustomizado.objects.get(id=request.user_id)

    try:
        credencial_concessionaria = CredencialConcessionaria.objects.get(
            cliente=cliente
        )
    except CredencialConcessionaria.DoesNotExist:
        credencial_concessionaria = None

    if cliente:
        try:
            credencial_inversor = CredencialInversor.objects.get(
                cliente=cliente
            )
        except CredencialInversor.DoesNotExist:
            credencial_inversor = None
    else:
        credencial_inversor = None

    if not form_usuario:
        form_usuario = UsuarioCustomizadoForm(
            instance=usuario, cliente_id=context['client_id']
        )
    if not form_credencial_inversor:
        form_credencial_inversor = CredencialInversorForm(
            instance=credencial_inversor, cliente_id=context['client_id']
        )
    if not form_senha:
        form_senha = AtualizarSenhaForm(request.user)
    if not form_credencial_concessionaria:
        if context.get('client_id'):
            cliente = Cliente.objects.get(id=context['client_id'])
            form_credencial_concessionaria = CredencialConcessionariaForm(
                instance=credencial_concessionaria,
                initial={'geracao_projeto': cliente.geracao_media_projeto},
                user_type=request.user_type,
            )
        else:
            form_credencial_concessionaria = CredencialConcessionariaForm(
                instance=credencial_concessionaria, user_type=request.user_type
            )

    context['form_usuario'] = form_usuario
    context['form_credencial_concessionaria'] = form_credencial_concessionaria
    context['form_credencial_inversor'] = form_credencial_inversor
    context['form_senha'] = form_senha

    # O usuário logado é uma empresa
    if request.user_type == 'admin':

        if not usuario:
            form_criar_usuario = CriarUsuarioCustomizadoForm()
            context['form_criar_usuario'] = form_criar_usuario

        # Filtrar as relações que têm a empresa correspondente
        if request.user_empresa:
            relacoes = RelacaoClienteEmpresa.objects.filter(
                empresa_id=request.user_empresa
            )
        else:
            relacoes = RelacaoClienteEmpresa.objects.all()
        # Agora, obter todos os IDs de clientes relacionados à empresa
        clientes_ids = relacoes.values_list('cliente_id', flat=True)

        # TODO: Aqui precisa ser ajustado para trazer usuários apenas da empresa logado.
        # Finalmente, obter todos os clientes com IDs correspondentes
        clientes = Cliente.objects.filter(id__in=clientes_ids).order_by(
            'plant_name'
        )
        # print(clientes)
        context['clientes'] = clientes
        context['user_empresa'] = request.user_empresa

    context['user_type'] = request.user_type
    context['username'] = request.username

    return render(request, 'clientes/profile_user.html', context=context)


def atualizar_tab(request):
    """
    Atualiza e retorna os dados necessários para a exibição da tabela de consumo e geração na interface do usuário.

    Args:
        request: Objeto HttpRequest contendo detalhes sobre a solicitação.

    Returns:
        HttpResponse: Resposta HTTP contendo os dados atualizados em formato JSON.
        
    Notas:
        - Utiliza o método HTTP POST para receber dados em formato JSON.
        - Realiza cálculos e análises para fornecer informações detalhadas sobre o consumo e geração de energia.
        - Lida com possíveis erros, como falha na decodificação JSON.

    """
    somar_economia = False
    economia = {}
    problema = False
    acao_necessaria = False
    info_adicional = False
    key_error = False
    # Inicialize as listas para armazenar as médias de 'consumo_total'
    medias_consumo_total_2023 = []
    medias_consumo_total_2022 = []
    # Inicialize as listas para armazenar os valores de 'consumo_total'
    consumo_total_2023 = []
    consumo_total_2022 = []
    meses_que_se_repetem = None

    if request.method == 'POST':
        try:
            # Recupere os dados enviados como JSON
            data = request.body.decode('utf-8')
            cliente = json.loads(data)
            # print('cliente ', cliente)

            if cliente:
                # print(cliente)
                instalacoes = Instalacao.objects.filter(
                    cliente__id=cliente[-1]
                )
                dados_cliente = Cliente.objects.filter(id=cliente[-1])

                data = {}

                if instalacoes:

                    if instalacoes.count() > 1:
                        somar_economia = True

                    for instalacao in instalacoes:

                        queryset_consumos = Consumo.objects.filter(
                            instalacao=instalacao
                        )

                        num_meses = queryset_consumos.count()
                        num_meses_graficos = 13
                        #printl("NUM MESES ;;;;;;;;;;" , num_meses)
                        consumos = queryset_consumos.order_by('-mes_ano')[:num_meses]
                        
                        tarifa = next(
                            (
                                c.tarifa
                                for c in consumos
                                if c.tarifa is not None
                            ),
                            None,
                        )
                        # print('#####CONSUMOS#####', consumos)
                        printl('#####TARIFA#####', tarifa)

                        # Obter os valores de mes_ano dos últimos 13 meses em Consumo
                        # meses_consumo = Consumo.objects.filter(instalacao=instalacao).order_by('-mes_ano')[:13].values_list('mes_ano', flat=True)
                        # Mesma variável montada sem consulta ao banco de dados
                        meses_consumo = list(c.mes_ano for c in consumos[:num_meses])

                        # Extrair o mês e o ano dos valores de mes_ano
                        meses_consumo = [
                            (x.year, x.month) for x in meses_consumo
                        ]
                        printl(
                            '¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨ MESES CONSUMO',
                            meses_consumo,
                        )

                        # Criar uma expressão Q complexa para filtrar os registros de Injeção com base nas combinações de ano e mês
                        q_expression = Q()
                        for year, month in meses_consumo:
                            q_expression |= Q(year=year, month=month)

                        dias_leitura = Injecao.objects.filter(
                            instalacao=instalacao
                        ).order_by('-mes_referencia')[:num_meses]

                        # Cria um dicionário vazio para armazenar os resultados
                        resultados = {}

                        # Itera sobre cada objeto 'injecao' retornado pela consulta
                        for i in range(len(dias_leitura)):
                            # Obtém a data de referência para esta 'injecao'
                            mes_referencia = dias_leitura[i].mes_referencia
                            printl(
                                '++++++++++++++++++++ MES REFERENCIA',
                                mes_referencia,
                            )

                            # Obtém a data de leitura anterior para esta 'injecao'
                            data_leitura_anterior = dias_leitura[
                                i
                            ].data_leitura_anterior

                            if (
                                dias_leitura[i].tipo_instalacao
                                == 'Beneficiada'
                            ):
                                soma_geracao = 0

                            else:

                                # Calcular o número de dias entre data_leitura_anterior e mes_referencia
                                diferenca_dias_total = (
                                    mes_referencia - data_leitura_anterior
                                ).days

                                ultimo_registro_geracao = (
                                    Geracao.objects.filter(
                                        cliente__id=cliente[-1]
                                    ).latest('timestamp')
                                )

                                # Calcular a diferença entre o último timestamp e mes_referencia
                                diferenca_dias = (
                                    mes_referencia
                                    - ultimo_registro_geracao.timestamp
                                ).days

                                # Calcular o mínimo de dias necessários para mais de 90% dos dias
                                minimo_dias_necessarios = int(
                                    diferenca_dias_total * 0.1
                                )

                                # Verificar se a diferença é maior que o mínimo de dias
                                if diferenca_dias > minimo_dias_necessarios:
                                    # print(f"A diferença entre o último registro ({ultimo_registro_geracao.timestamp}) e mes_referencia é maior do que {minimo_dias_necessarios} dias. Os valores podem estar comprometidos.")
                                    # Emitir um aviso aqui, por exemplo, usando a biblioteca logging.
                                    problema = True
                                    acao_necessaria = 'DADOS INCONSISTENTES: Necessária atualização de geração ou há falta de comunicação do datalogger'
                                    key_error = 'falta_geracao'

                                # print('data leitura anterior', data_leitura_anterior, 'mes referencia', mes_referencia, 'diferenca dias', diferenca_dias, 'minimo dias necessario', minimo_dias_necessarios)
                                # Filtra os objetos 'geracao' que correspondem ao intervalo de tempo e soma os valores

                                queryset = Geracao.objects.filter(
                                    cliente__id=cliente[-1],
                                    timestamp__gte=data_leitura_anterior,
                                    timestamp__lt=mes_referencia,
                                ).exclude(
                                    Q(energystamp=None) | Q(energystamp=0)
                                )

                                soma_geracao = queryset.aggregate(
                                    soma=Sum('energystamp') / 1000
                                )['soma']
                                count = queryset.aggregate(count=Count('id'))[
                                    'count'
                                ]

                                # Converta mes_referencia para o formato (ano, mês)
                                mes_referencia_formatado = (
                                    mes_referencia.year,
                                    mes_referencia.month,
                                )

                                if (
                                    diferenca_dias_total != count
                                    and mes_referencia_formatado
                                    != meses_consumo[0]
                                ):
                                    printl(
                                        '@@@@@@@@@@@ erro no mês',
                                        dt.strftime(mes_referencia, '%m/%Y'),
                                        diferenca_dias_total,
                                        count,
                                    )
                                    printl(
                                        '@@@ mes referencia',
                                        mes_referencia,
                                        '@@@ data_leitura_anterior',
                                        data_leitura_anterior,
                                    )
                                    problema = True
                                    acao_necessaria = '* Devido à falta de comunicação em alguns dias, seu autoconsumo pode ter dados inconsistentes.'
                                    key_error = 'autoconsumo_incompleto'
                                    if not info_adicional:
                                        info_adicional = []
                                    info_adicional.append(
                                        dt.strftime(mes_referencia, '%m/%Y')
                                    )
                                # TODO: Continuar daqui. Conseguir emitir essa diferença para o html
                                # printl('###### ### TESTE SOMA GERAÇÃO ####### ', data_leitura_anterior, mes_referencia, soma_geracao)

                            # Adiciona o resultado ao dicionário
                            resultados[mes_referencia] = soma_geracao
                            # print('resultados', resultados, 'mes_referencia', mes_referencia, 'data_leitura_anterior', data_leitura_anterior)

                        # print(resultados)
                        # Agora 'resultados' é um dicionário onde as chaves são as datas de referência e os valores são as somas correspondentes da tabela 'geracao'

                        # Filtrar os registros de Injecao com base nos valores de mes_ano em Consumo
                        injecoes = (
                            Injecao.objects.filter(instalacao=instalacao)
                            .annotate(
                                year=ExtractYear('mes_referencia'),
                                month=ExtractMonth('mes_referencia'),
                            )
                            .filter(q_expression)
                        )

                        # Recuperar o primeiro valor da coluna 'tipo_instalacao'
                        tipo_instalacao = injecoes.values_list(
                            'tipo_instalacao', flat=True
                        ).first()

                        # Converter QuerySet para lista
                        injecoes_list = list(injecoes)

                        # Ordenar a lista por mes_referencia em ordem decrescente
                        injecoes_list.sort(key=lambda x: x.mes_referencia, reverse=True)

                        # Pegar os 13 últimos registros
                        ultimos_13_registros = injecoes_list[:num_meses_graficos]

                        # Calcular o valor máximo de energia_injetada_fora_ponta para os 13 últimos registros
                        max_injecao = max(registro.energia_injetada_fora_ponta for registro in ultimos_13_registros)
                        
                        consumos_list = queryset_consumos.order_by('-mes_ano')[:num_meses_graficos]

                        # Obter o valor máximo de valor para calcular o percentual
                        max_valor = consumos_list.aggregate(Max('valor'))[
                            'valor__max'
                        ]
                        if max_valor < 200:
                            max_valor = 400

                        injecoes_dict = {}
                        for injecao in injecoes:
                            mes_referencia = injecao.mes_referencia.strftime(
                                '%m/%Y'
                            )
                            percent_inject = (
                                max_injecao
                                if max_injecao == 0
                                else (
                                    injecao.energia_injetada_fora_ponta
                                    / max_injecao
                                )
                                * 100
                            )
                            # Obtém a soma do dicionário 'resultados' usando 'mes_referencia' como chave
                            soma_geracao = resultados.get(
                                injecao.mes_referencia
                            )
                            injecoes_dict[mes_referencia] = {
                                'energia_injetada_fora_ponta': injecao.energia_injetada_fora_ponta,
                                'percent_inject': percent_inject,
                                'energia_recebida_fora_ponta': injecao.energia_recebida_fora_ponta,
                                # Adiciona a soma ao dicionário
                                'soma_geracao': soma_geracao,
                                'saldo_acumulado': injecao.saldo_acumulado,
                            }

                        # print(injecoes_dict)

                        max_consumo = consumos_list.aggregate(Max('consumo'))[
                            'consumo__max'
                        ]

                        consumos_percent = []
                        for consumo in consumos:
                            percent = (consumo.consumo / max_consumo) * 100

                            mes_ano = consumo.mes_ano.strftime('%m/%Y')
                            injecao_data = injecoes_dict.get(
                                mes_ano,
                                {
                                    'energia_injetada_fora_ponta': 0,
                                    'percent_inject': 0,
                                    'energia_recebida_fora_ponta': 0,
                                    'soma_geracao': 0,
                                    'saldo_acumulado': 0,
                                },
                            )

                            soma_geracao_total = (
                                0
                                if not injecao_data['soma_geracao']
                                else round(injecao_data['soma_geracao'], 2)
                            )
                            # tarifa = 0 if not consumo.tarifa else consumo.tarifa

                            # print('###### mes ano', mes_ano)
                            # print('consumo', float(consumo.consumo))
                            # print('soma_geracao', float(soma_geracao_total))
                            # print('energia injetada', float(injecao_data['energia_injetada_fora_ponta']))
                            # print('energia recebida', injecao_data['energia_recebida_fora_ponta'])
                            # print('tipo', tipo_instalacao)
                            # print('tarifa', tarifa)

                            if tipo_instalacao == 'Geradora':
                                # Calcular o valor de energia_faturada_fora_ponta
                                energia_faturada_fora_ponta = (
                                    consumo.consumo
                                    - injecao_data[
                                        'energia_injetada_fora_ponta'
                                    ]
                                )
                                if somar_economia and mes_ano in economia:
                                    economia[mes_ano] += (
                                        (
                                            float(consumo.consumo)
                                            + float(soma_geracao_total)
                                            - float(
                                                injecao_data[
                                                    'energia_injetada_fora_ponta'
                                                ]
                                            )
                                        )
                                        * tarifa
                                    ) - consumo.valor
                                else:
                                    economia[mes_ano] = (
                                        (
                                            float(consumo.consumo)
                                            + float(soma_geracao_total)
                                            - float(
                                                injecao_data[
                                                    'energia_injetada_fora_ponta'
                                                ]
                                            )
                                        )
                                        * tarifa
                                    ) - consumo.valor
                            else:
                                energia_faturada_fora_ponta = (
                                    consumo.consumo
                                    - injecao_data[
                                        'energia_recebida_fora_ponta'
                                    ]
                                )
                                if somar_economia and mes_ano in economia:
                                    economia[mes_ano] += (
                                        float(
                                            injecao_data[
                                                'energia_recebida_fora_ponta'
                                            ]
                                        )
                                        * tarifa
                                    )
                                else:
                                    economia[mes_ano] = (
                                        float(
                                            injecao_data[
                                                'energia_recebida_fora_ponta'
                                            ]
                                        )
                                        * tarifa
                                    )

                            # Calcular o percentual de valor
                            valor_percent = (consumo.valor / max_valor) * 100

                            if dados_cliente.first().geracao_media_projeto:
                                consumo_inicial_projeto = (
                                    dados_cliente.first().geracao_media_projeto
                                )
                            else:
                                consumo_inicial_projeto = 0
                                problema = True
                                acao_necessaria = 'DADOS INCONSISTENTES: É necessário que a Geração Média do Projeto esteja definida no perfil do cliente'
                                key_error = 'falta_geracao_media'

                            # print('consumo_inicial_projeto', consumo_inicial_projeto)
                            consumos_percent.append(
                                {
                                    'mes_ano': mes_ano,
                                    'mes_ano_original': consumo.mes_ano,
                                    'consumo': consumo.consumo,
                                    'percent': round(percent, 2),
                                    'valor': '{:.2f}'.format(consumo.valor),
                                    'energia_injetada_fora_ponta': injecao_data[
                                        'energia_injetada_fora_ponta'
                                    ],
                                    'percent_inject': round(
                                        injecao_data['percent_inject'], 2
                                    ),
                                    'energia_faturada_fora_ponta': round(
                                        energia_faturada_fora_ponta, 2
                                    ),
                                    'percent_valor': round(valor_percent, 2),
                                    'soma_geracao': soma_geracao_total,
                                    'saldo_acumulado': injecao_data[
                                        'saldo_acumulado'
                                    ],
                                    'consumo_inicial_projeto': consumo_inicial_projeto,  # geracao_media_projeto
                                }
                            )

                        # print(consumos_percent)

                        for item in consumos_percent:
                            if tipo_instalacao == 'Geradora':
                                item['consumo_total'] = round(
                                    item['consumo']
                                    + item['soma_geracao']
                                    - item['energia_injetada_fora_ponta'],
                                    2,
                                )
                            else:
                                item['consumo_total'] = round(
                                    item['consumo'], 2
                                )
                        #printl('CONSUMOS PERCENT ->>>>',consumos_percent)
                        # Encontrar o valor máximo de consumo_total
                        max_consumo_total = max(
                            item['consumo_total'] for item in consumos_percent
                        )

                        # Calcular a porcentagem relativa para cada item
                        for item in consumos_percent:
                            item['percent_consumo_total'] = round(
                                (item['consumo_total'] / max_consumo_total)
                                * 100,
                                2,
                            )

                        consumos_sorted = sorted(
                            consumos_percent,
                            key=lambda x: x['mes_ano_original'],
                            reverse=True,
                        )

                        data[
                            f'{instalacao.codigo} - {tipo_instalacao}'
                        ] = consumos_sorted

                        for chave, inst_data in data.items():
                            max_consumo_total_inst = max(
                                item['consumo_total'] for item in inst_data
                            )

                            for item in inst_data:
                                percent_consumo_total_inst = item[
                                    'percent_consumo_total'
                                ]

                                # Calcular as proporções das porcentagens
                                proporcao_consumo = (
                                    item['consumo'] / max_consumo_total_inst
                                )
                                proporcao_geracao = (
                                    item['soma_geracao']
                                    - item['energia_injetada_fora_ponta']
                                ) / max_consumo_total_inst

                                # Calcular as porcentagens proporcionalmente ao percent_consumo_total
                                item['percent_ct_consumo'] = round(
                                    proporcao_consumo
                                    * percent_consumo_total_inst,
                                    2,
                                )
                                item['percent_ct_geracao'] = round(
                                    proporcao_geracao
                                    * percent_consumo_total_inst,
                                    2,
                                )
                                
                        # Inicialize dois conjuntos para armazenar os meses que aparecem em 2023 e 2022
                        meses_2023 = set()
                        meses_2022 = set()

                        # Percorra cada registro no JSON
                        for registro in consumos_sorted:
                            mes_ano = dt.strptime(registro['mes_ano'], '%m/%Y')
                            if mes_ano.year == 2023:
                                # Adicione o mês ao conjunto de 2023
                                meses_2023.add(mes_ano.month)
                            elif mes_ano.year == 2022:
                                # Adicione o mês ao conjunto de 2022
                                meses_2022.add(mes_ano.month)

                        # Encontre a interseção dos dois conjuntos
                        meses_que_se_repetem = meses_2023.intersection(meses_2022)
                        #printl(')()()()()()()()()()()(', instalacao.id, meses_que_se_repetem)
                        
                        if meses_que_se_repetem:
                        
                            # Percorra cada registro no JSON
                            for registro in consumos_sorted:
                                mes_ano = dt.strptime(registro['mes_ano'], '%m/%Y')
                                if mes_ano.year == 2023:
                                    # Adicione o 'consumo_total' à lista de 2023
                                    consumo_total_2023.append(registro['consumo_total'])
                                elif mes_ano.year == 2022 and mes_ano.month in meses_que_se_repetem:
                                    # Adicione o 'consumo_total' à lista de 2022
                                    consumo_total_2022.append(registro['consumo_total'])

                            # Calcule a média do 'consumo_total' para cada ano
                            media_consumo_total_2023 = sum(consumo_total_2023) / len(consumo_total_2023) if consumo_total_2023 else 0
                            media_consumo_total_2022 = sum(consumo_total_2022) / len(consumo_total_2022) if consumo_total_2022 else 0

                            # Adicione as médias às listas
                            if consumo_total_2023:
                                medias_consumo_total_2023.append(media_consumo_total_2023)
                            if consumo_total_2022:
                                medias_consumo_total_2022.append(media_consumo_total_2022)

                    # Obter o mês e o ano atual
                    agora = dt.now()
                    mes_atual = agora.strftime('%m/%Y')

                    # Iterar sobre todas as chaves no dicionário
                    for chave in data:
                        # Obter o primeiro 'mes_ano' para a chave atual
                        primeiro_mes_ano = data[chave][0]['mes_ano']

                        # Comparar o primeiro 'mes_ano' com o mês e o ano atual
                        if primeiro_mes_ano != mes_atual:
                            problema = True
                            acao_necessaria = 'DADOS INCONSISTENTES: Uma ou mais contas ainda não tiveram leitura esse mês. Análise disponível apenas para o mês passado'
                            info_adicional = primeiro_mes_ano
                            key_error = 'falta_leitura'
                            
                    consumoAtual = 0
                    consumoAnoPassado = 0
                    mesAnoAtual = '11/2023'
                    mesAnoPassado = '11/2022'

                    for instalacao, detalhes in data.items():
                        for index, detalhe in enumerate(detalhes):
                            try:
                                consumo = float(detalhe['consumo_total'])
                                print('consumo_total ' + str(consumo) + ' mes_ano ' + detalhe['mes_ano'] + ' mesAnoAtual ' + mesAnoAtual)
                            except ValueError:
                                print('Valor inválido para consumo_total: ' + detalhe['consumo_total'])
                                continue

                            if detalhe['mes_ano'] == mesAnoAtual:
                                consumoAtual += consumo
                            elif detalhe['mes_ano'] == mesAnoPassado:
                                consumoAnoPassado += consumo
                                
                    printl('consumoatual consumoanopassado', consumoAtual, consumoAnoPassado)
                    
                    # Crie uma lista dos últimos 12 meses (ou menos)
                    meses = []
                    for i in range(12):
                        data_atual = dt.now() - relativedelta(months=i)
                        mes = data_atual.month
                        ano = data_atual.year
                        if mes < 10: 
                            mes = '0' + str(mes)
                        meses.append(str(mes) + '/' + str(ano))

                    # Crie um dicionário para armazenar o consumo total para cada mês
                    consumo_por_mes = {}

                    for instalacao, detalhes in data.items():
                        for index, detalhe in enumerate(detalhes):
                            # Verifique se o mês do detalhe está dentro dos últimos 12 meses
                            if detalhe['mes_ano'] in meses:
                                try:
                                    consumo = float(detalhe['consumo_total'])
                                    if detalhe['mes_ano'] in consumo_por_mes:
                                        consumo_por_mes[detalhe['mes_ano']] += consumo
                                    else:
                                        consumo_por_mes[detalhe['mes_ano']] = consumo
                                except ValueError:
                                    print('Valor inválido para consumo_total: ' + detalhe['consumo_total'])
                    
                    # Limita para os 13 últimos meses
                    for instalacao in data:
                        data[instalacao] = data[instalacao][:13]       
                    
                    printl('consumo_total_2022', consumo_total_2022)
                    printl('consumo_total_2023', consumo_total_2023)
                    # Calcule a média do consumo total
                    soma_consumo = sum(consumo_por_mes.values())
                    consumo_medio_anual = soma_consumo / len(consumo_por_mes)
                    printl('soma_consumo consumo_medio_anual', soma_consumo, consumo_medio_anual)
                    porcentagem_consumo_medio_anual = ((consumo_medio_anual - consumo_inicial_projeto) / consumo_inicial_projeto) * 100
                    printl('porcentagem_consumo_medio_anual', porcentagem_consumo_medio_anual)

                    data['info'] = {}
                    data['info']['economia'] = economia
                    data['info']['problema'] = problema
                    data['info']['acao_necessaria'] = acao_necessaria
                    data['info']['info_adicional'] = info_adicional
                    data['info']['key_error'] = key_error

                    # print(economia)
                    #printl(data_json)
                    
                    # Calcule a média geral de todas as instalações
                    media_geral_consumo_total_2023 = sum(medias_consumo_total_2023) / len(medias_consumo_total_2023)
                    media_geral_consumo_total_2022 = sum(medias_consumo_total_2022) / len(medias_consumo_total_2022)

                    # Compare as médias gerais
                    diferenca = media_geral_consumo_total_2023 - media_geral_consumo_total_2022
                    percentagem_dif_medias = (diferenca / media_consumo_total_2022) * 100
                    printl('media_geral_consumo_total_2022', media_geral_consumo_total_2022)
                    printl('media_geral_consumo_total_2023', media_geral_consumo_total_2023)
                    printl('diferenca', diferenca)
                    printl('percentagem_dif_medias', percentagem_dif_medias)
                    
                    data['previsao'] = {}
                    if percentagem_dif_medias:
                        data['previsao']['percentagem_dif_medias'] = round(percentagem_dif_medias, 2)
                        data['previsao']['percentagem_media_anual'] = round(float(percentagem_dif_medias/12), 2)
                    else: 
                        data['previsao']['percentagem_dif_medias'] = 0
                        data['previsao']['percentagem_media_anual'] = 0
                    if meses_que_se_repetem :
                        data['previsao']['meses_analisados'] = len(meses_que_se_repetem)
                        
                        
                    data_json = json.dumps(data, default=datetime_serializer)
                        
                        
                    response = HttpResponse(
                        data_json, content_type='application/json'
                    )

                    return response

                else:
                    return JsonResponse({})

            else:
                return JsonResponse({})

        except json.JSONDecodeError:
            # Caso haja um erro ao decodificar o JSON
            error_response = {'error': 'Erro ao decodificar JSON.'}
            return JsonResponse(error_response, status=400)
