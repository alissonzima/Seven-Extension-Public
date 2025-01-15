import base64
import json
import logging
import os
import re
import traceback
from datetime import datetime as dt
from io import BytesIO
from time import sleep

import pandas as pd
import pytz
import requests
from apps.clientes.methods import printl
from apps.clientes.models import Consumo, Injecao, Instalacao
from core.custom_exceptions import CPFouCNPJNaoEncontradoError, TelNaoEncontradoError
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# cria um objeto de fuso horário para o fuso horário desejado
fuso = pytz.timezone('America/Sao_Paulo')
execucoes = 'Iniciando -- '

def busca_rge(credencial, cliente_info):
    """
    Realiza a busca de dados específicos relacionados à concessionária RGE.

    Esta função utiliza Selenium para realizar uma série de interações automatizadas em um site específico
    da CPFL RGE. Ela faz login no site, navega por diferentes páginas, extrai informações e realiza
    operações diversas. Além disso, realiza requisições HTTP para obter informações adicionais.
    Essa função é necessária pois para obter o token de validaçao do site, ele utiliza um javascript obscurecido.
    Até conseguirmos decifrar o método correto de login, é necessário utiliar Selenium.

    Args:
        credencial (object): Objeto contendo credenciais de acesso.
        cliente_info (dict): Dicionário com informações específicas do cliente.

    Raises:
        Exception: Se ocorrerem problemas durante a execução, um aviso é enviado ao administrador e uma exceção é levantada.

    Example:
        >>> busca_rge(credencial, cliente_info)
    """
    max_tentativas = 3
    instalacoes = {}
    values = {}
    global execucoes

    for tentativa in range(max_tentativas):

        try:

            data_str = '00/00/0000'

            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 OPR/98.0.0.0'

            email = credencial.usuario
            password = credencial.senha

            # Configura o nível de registro do urllib3
            logging.getLogger('urllib3').setLevel(logging.WARNING)

            options = webdriver.ChromeOptions()

            #options.add_argument('--headless=new')
            # Set the custom User-Agent
            options.add_argument(f'--user-agent={user_agent}')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')

            # Cria uma instância do driver do navegador Chrome com registro de mensagens habilitado
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

            # Detecta o sistema operacional
            if os.name == 'nt':
                # 'nt' é para Windows
                driver_path = r'C:\chromedriver\chromedriver.exe'
            else:
                # Assume que é um sistema baseado em Unix (como Linux)
                driver_path = '/usr/bin/chromedriver'

            service = Service(driver_path)

            # Inicializar o driver do navegador (certifique-se de ter o driver correto para o navegador instalado)
            driver = webdriver.Chrome(service=service, options=options)

            # Carregar a página
            driver.get('https://www.cpfl.com.br/b2c-auth/login')

            def login_rge():
                """
                Realiza o login no site da RGE.

                Este método utiliza Selenium para interagir com os campos de e-mail, senha e botão de login
                no site da RGE. Após o login, aguarda até que a URL desejada seja alcançada.

                Raises:
                    TimeoutException: Se a página não carregar dentro de 15 segundos.

                Example:
                    >>> login_rge()
                """
                global execucoes
                execucoes += ' login_rge() '

                # Aguarde até que o campo de e-mail esteja visível e interagível
                email_field = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'input#signInName')
                    )
                )

                # Aguarde até que o campo de senha esteja visível e interagível
                password_field = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'input#password')
                    )
                )

                # Aguarde até que o botão de login esteja visível e interagível
                login_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'button#next')
                    )
                )

                # Preencha os campos de e-mail e senha
                email_field.send_keys(email)
                password_field.send_keys(password)

                # Envie o formulário de login
                login_button.click()

                # Aguardar até que a URL desejada seja alcançada após o login
                desired_url1 = (
                    'https://www.cpfl.com.br/agencia/area-cliente/cadastro'
                )
                desired_url2 = (
                    'https://servicosonline.cpfl.com.br/agencia-webapp/#/home'
                )
                desired_url3 = (
                    'https://www.cpfl.com.br/agencia-virtual/pagina-inicial'
                )

                try:
                    wait = WebDriverWait(driver, 15)  # Aguardar 15 segundos
                    wait.until(
                        lambda driver: driver.current_url == desired_url1
                        or driver.current_url == desired_url2
                        or driver.current_url == desired_url3
                    )
                except TimeoutException:
                    # Se a página não carregar dentro de 15 segundos, recarregue a página
                    driver.refresh()
                    wait = WebDriverWait(driver, 15)  # Aguardar 15 segundos
                    wait.until(
                        lambda driver: driver.current_url == desired_url1
                        or driver.current_url == desired_url2
                    )

            def necessidade_cpf():
                """
                Verifica a necessidade de intervenção relacionada ao CPF ou CNPJ durante a execução.

                Esta função utiliza Selenium para verificar a existência de um elemento específico ("TITULAR") na página.
                Se o elemento existir, ela fecha um pop-up (caso exista) e interage com um combobox, selecionando o valor
                correspondente ao CPF ou CNPJ armazenado no banco de dados. Caso o CPF ou CNPJ não seja encontrado, ou
                seja incorreto, uma exceção é levantada.

                Raises:
                    CPFouCNPJNaoEncontradoError: Se o CPF ou CNPJ não for encontrado no banco de dados ou for incorreto.

                Example:
                    >>> necessidade_cpf()
                """
                # Defina element como None antes do bloco try
                element = None
                global execucoes

                # Verifique se o elemento existe
                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//*[contains(text(), 'TITULAR')]")
                        )
                    )
                    printl('Encontrado campo TITULAR')
                except:
                    printl('Não são necessárias intervenções')

                # Se o elemento existir, clique no combobox de seleção
                if element:
                    execucoes += ' necessidade_cpf() '

                    # Encontre o botão de fechar e clique nele
                    close_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (
                                By.CSS_SELECTOR,
                                'button.onetrust-close-btn-handler',
                            )
                        )
                    )
                    close_button.click()

                    sleep(2)

                    select2 = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.CLASS_NAME, 'selection')
                        )
                    )
                    select2.click()

                    # Aguarde o carregamento dos elementos dropdown
                    sleep(2)

                    # Busque o valor do cpf ou cnpj do seu banco de dados
                    cpf_cnpj = credencial.cpf_cnpj

                    if cpf_cnpj:

                        # Clique no elemento que contém esse código
                        dropdown_element = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (
                                    By.XPATH,
                                    f"//*[contains(text(), '{cpf_cnpj}')]",
                                )
                            )
                        )
                        dropdown_element.click()
                        # Aguarde o carregamento dos elementos radiobutton
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located(
                                (
                                    By.CSS_SELECTOR,
                                    "input[type='radio'][id^='instalacao-']",
                                )
                            )
                        )

                    else:
                        raise CPFouCNPJNaoEncontradoError(
                            'CPF ou CNPJ não encontrados no banco de dados ou incorreto. Favor corrigir.'
                        )

            login_rge()
            execucoes += ' login '

            # Carregar a página
            driver.get(
                'https:/\/www.cpfl.com.br/agencia/area-cliente/selecionar-perfil-instalacao'
            )

            necessidade_cpf()
            execucoes += ' cpf '

            # Localize todos os elementos <div> que contêm os elementos de rádio
            divs_instalacoes = WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div.form-item-instalacoes')
                )
            )

            # Crie uma lista para armazenar os rádios ativos
            ids_radios_ativos = []

            # Itere sobre os elementos <div> encontrados
            for div_instalacao in divs_instalacoes:
                execucoes += ' div_instalacoes '

                # Encontre o elemento de rádio dentro deste <div> atual
                radio = div_instalacao.find_element(
                    By.CSS_SELECTOR, "input[type='radio'][id^='instalacao-']"
                )

                # Encontre o elemento <label> associado a este rádio
                label = div_instalacao.find_element(
                    By.CSS_SELECTOR,
                    f"label[for='{radio.get_attribute('id')}']",
                )

                # Verifique se o texto do elemento <label> contém "Ativa"
                if 'Ativa' in label.text:
                    ids_radios_ativos.append(radio.get_attribute('id'))

            # Localize os elementos de rádio novamente após a recarga da página
            for id_radio in ids_radios_ativos:
                execucoes += ' ids_radios_ativos '

                radio = driver.find_element(
                    By.CSS_SELECTOR, f"input[type='radio'][id='{id_radio}']"
                )
                execucoes += ' ids_radios_ativosradio ' + radio.get_attribute('name')

                # Extract the number after 'instalacao-' from the radio button id attribute
                codigo = radio.get_attribute('id').split('-')[1]
                execucoes += ' ids_radios_ativoscodigo ' + codigo

                # Clica no elemento radio atual
                driver.execute_script('arguments[0].click();', radio)
                button = driver.find_element(By.ID, 'goto-page-btn')
                execucoes += ' ids_radios_ativosbutton ' + button.get_attribute('id')


                driver.execute_script('arguments[0].click();', button)

                # Aguardar até que a URL desejada seja alcançada após o login
                desired_url = (
                    #'https://servicosonline.cpfl.com.br/agencia-webapp/#/home'
                    'https://www.cpfl.com.br/agencia-virtual/pagina-inicial'
                )
                
                sleep(5)

                try:
                    execucoes += ' ' + driver.current_url
                    wait = WebDriverWait(driver, 55)
                    wait.until(EC.url_to_be(desired_url))
                
                except:
                    execucoes += ' termos de uso '
                    
                    if (driver.current_url == 'https://www.cpfl.com.br/agencia/area-cliente/cadastro'):
                        
                        termos_de_uso = driver.find_element(
                            By.ID, 
                            'edit-ts-cs'
                        )
                        termos_de_uso.click()
                        
                        fone = credencial.fone
                        
                        if fone :
                        
                            fone_field = driver.find_element(
                                By.ID, 
                                'edit-celular'
                            )
                            
                            if fone_field.get_attribute('value') == '':
                                
                                driver.execute_script("arguments[0].setAttribute('value', '{}')".format(fone), fone_field)
                            
                            btn_avancar = driver.find_element(
                                By.ID,
                                'goto-page-btn'
                            )
                            btn_avancar.click()
                        else:
                            raise TelNaoEncontradoError(
                                'Telefone não encontrado no banco de dados ou incorreto. Favor corrigir.'
                            )
                    
                    else :
                        # Espere até que o botão esteja presente e então clique nele
                        button = WebDriverWait(driver, 60).until(
                            EC.presence_of_element_located((By.ID, 'btnEntrar'))
                        )
                        # print('button', button)
                        driver.execute_script('arguments[0].click();', button)
                        login_rge()
                        # Carregar a página
                        driver.get(
                            'https:/\/www.cpfl.com.br/agencia/area-cliente/selecionar-perfil-instalacao'
                        )
                        necessidade_cpf()
                        radio = driver.find_element(
                            By.CSS_SELECTOR,
                            f"input[type='radio'][id='{id_radio}']",
                        )
                        # TODO: Fazer um método e remover a parte repetida abaixo
                        # Extract the number after 'instalacao-' from the radio button id attribute
                        codigo = radio.get_attribute('id').split('-')[1]

                        # Clica no elemento radio atual
                        driver.execute_script('arguments[0].click();', radio)
                        button = driver.find_element(By.ID, 'goto-page-btn')

                        driver.execute_script('arguments[0].click();', button)

                wait = WebDriverWait(driver, 30)
                wait.until(EC.url_to_be(desired_url))
                execucoes += ' minha conta '
                
                driver.set_window_size(1920, 1080)

                #driver.save_screenshot('minha conta.png')
                minha_conta = WebDriverWait(driver, 30).until(
                        EC.element_to_be_clickable(
                            (
                                By.NAME,
                                'minha conta',
                            )
                        )
                    )
                driver.execute_script("arguments[0].click();", minha_conta)
                execucoes += ' minimicro geracao '
                minimicro_geracao = WebDriverWait(driver, 30).until(
                            EC.element_to_be_clickable(
                                (
                                    By.NAME,
                                    'micro/minigeração - histórico',
                                )
                            )
                        )
                driver.execute_script("arguments[0].click();", minimicro_geracao)
                
                #driver.get(
                #    'https://www.cpfl.com.br/cpfl-auth/redirect-arame-servicos?servico=micro/minigeracao-historico'
                #)
                
                desired_url = 'https://servicosonline.cpfl.com.br/agencia-webapp/#/micro-mini-geracao-relatorio'
                
                try:
                    wait = WebDriverWait(driver, 45)
                    wait.until(EC.url_to_be(desired_url))
                except TimeoutException:
                    driver.refresh()
                    wait = WebDriverWait(driver, 45)
                    wait.until(EC.url_to_be(desired_url))

                # Obtém as mensagens de registro do navegador
                logs = driver.get_log('performance')
                bearer_token = ''
                
                for log in logs:

                    message = json.loads(log['message'])['message']

                    if message['method'] == 'Network.requestWillBeSent':

                        # Captura a requisição JSON
                        request = message['params']['request']
                        headers = request.get('headers')
                        if headers:
                            token = headers.get('Authorization')
                            if token:
                                bearer_token = token
                        url = request['url']
                        if 'agencia-webapi' in url:
                            printl(url)
                        if (
                            url
                            #== 'https://servicosonline.cpfl.com.br/agencia-webapi/api/historico-contas/validar-situacao'
                            == 'https://servicosonline.cpfl.com.br/agencia-webapi/api/micro-mini-geracao/validar-situacao'
                        ):
                            # Obtém o payload da requisição JSON
                            payload = request.get('postData')
                            if payload:
                                data = json.loads(payload)
                                # Extrai os valores das chaves desejadas
                                keys = [
                                    'CodigoFase',
                                    'IndGrupoA',
                                    'Situacao',
                                    'ContaContrato',
                                    'CodigoClasse',
                                    'CodEmpresaSAP',
                                    'Instalacao',
                                    'ParceiroNegocio',
                                ]
                                values = {key: data.get(key) for key in keys}

                values['RetornarDetalhes'] = True
                # print(bearer_token)
                # print(values)
                execucoes += bearer_token
                headers = {'authorization': bearer_token}

                json_data = values

                response = requests.post(
                    'https://servicosonline.cpfl.com.br/agencia-webapi/api/micro-mini-geracao/validar-situacao',
                    headers=headers,
                    json=json_data,
                )

                driver.get(
                    'https://www.cpfl.com.br/agencia/area-cliente/selecionar-perfil-instalacao'
                )

                if response.status_code != 200:
                    printl('Código de erro rge:', response.status_code)
                    continue

                # Check if an Instalacao object with this codigo already exists for the given cliente
                instalacao = Instalacao.objects.filter(
                    cliente=credencial.cliente, codigo=codigo
                ).first()

                # If an Instalacao object does not exist, create one
                if not instalacao:
                    # Localize o elemento label correspondente ao elemento radio atual
                    label = driver.find_element(
                        By.XPATH, f"//label[@for='instalacao-{codigo}']"
                    )

                    # Localize todos os elementos com a classe 'texto-simples' dentro do elemento label
                    texto_simples_elements = label.find_elements(
                        By.CLASS_NAME, 'texto-simples'
                    )

                    # Extraia o texto de cada elemento 'texto-simples' e junte-os em uma única string
                    endereco = ' '.join(
                        [element.text for element in texto_simples_elements]
                    )

                    # Crie um novo objeto Instalacao com o endereco extraído
                    instalacao = Instalacao(
                        cliente=credencial.cliente,
                        codigo=codigo,
                        endereco=endereco,
                    )
                    instalacao.save()
                    execucoes += ' instalacao_save '

                dados = response.json()

                protocolo = dados['Protocolo']

                # Obtenha a data atual
                now = dt.now()

                # Defina o dia como 1 para obter o primeiro dia do mês e ano atual
                first_day_of_month = now.replace(day=1)
                last_month = first_day_of_month - relativedelta(months=1)

                # Subtraia 13 meses da data atual
                thirteen_months_ago = first_day_of_month - relativedelta(
                    months=13
                )

                # Formate a data como desejar
                formatted_date = thirteen_months_ago.strftime('%d%m%Y')

                now = dt.now()

                params = {
                    'instalacao': values['Instalacao'],
                    'mesInicio': formatted_date,
                    'mesFim': now.strftime('%d%m%Y'),
                    'protocolo': protocolo,
                }

                url = f'https://servicosonline.cpfl.com.br/agencia-webapi/api/micro-mini-geracao/obter-relatorio-excel'

                response = requests.get(url, headers=headers, params=params)

                printl(response.json())

                # mes_referencia_excel = ''

                if response.json()['Success']:
                    excel_data_base64 = response.json()['Bytes']

                    # Decodifique os dados do arquivo Excel
                    excel_data = base64.b64decode(excel_data_base64)

                    # Crie um objeto BytesIO a partir dos dados em bytes
                    excel_file = BytesIO(excel_data)

                    # Leia os dados do arquivo Excel usando o pandas
                    df = pd.read_excel(excel_file)

                    # # Verifique se o DataFrame tem pelo menos duas linhas
                    # if len(df) >= 2:
                    #     # Se o DataFrame tiver pelo menos duas linhas, use os valores da segunda linha
                    #     row_index = 1
                    # else:
                    #     # Caso contrário, use os valores da primeira linha
                    #     row_index = 0

                    # # Acesse os valores da linha apropriada
                    # saldo_acumulado = df.at[row_index, 'Saldo Acumulado (Fora Ponta)']
                    # mes_referencia_excel = fuso.localize(datetime.datetime.strptime(df.at[row_index, 'Mês de referência'], '%m/%Y'))
                    # print(saldo_acumulado, mes_referencia_excel)
                execucoes += ' excel '
                injecoes = []

                for dado in dados['ListGeracoes']:
                    # print('#####################DADO##################', dado)
                    if dado['MesExpiracao'] == data_str:
                        mes_expiracao = None
                    else:
                        mes_expiracao = fuso.localize(
                            dt.strptime(dado['MesExpiracao'], '%d/%m/%Y')
                        )

                    # associa o fuso horário ao objeto de data/hora
                    mes_referencia = fuso.localize(
                        dt.strptime(dado['MesReferencia'], '%d/%m/%Y')
                    )

                    linha = df.loc[
                        df['Data de Leitura Atual'] == dado['MesReferencia']
                    ]
                    # print('mes_referencia', dado['MesReferencia'])

                    injecao = Injecao(
                        instalacao=instalacao,
                        tipo_geracao=dado['TipoGeracao'],
                        tipo_instalacao=dado['TipoInstalacao'],
                        mes_referencia=mes_referencia,
                        porcentagem=dado['Porcentagem'].strip(),
                        consumo_mensal_ponta=dado[
                            'ConsumoMensalPonta'
                        ].strip(),
                        consumo_mensal_fora_ponta=dado[
                            'ConsumoMensalForaPonta'
                        ].strip(),
                        energia_injetada_ponta=dado[
                            'EnergiaInjetadaPonta'
                        ].strip(),
                        energia_injetada_fora_ponta=dado[
                            'EnergiaInjetadaForaPonta'
                        ].strip(),
                        energia_recebida_ponta=dado[
                            'EnergiaRecebidaPonta'
                        ].strip(),
                        energia_recebida_fora_ponta=dado[
                            'EnergiaRecebidaForaPonta'
                        ].strip(),
                        creditos_utilizados_ponta=dado[
                            'CreditosUtilizadosPonta'
                        ].strip(),
                        creditos_utilizados_fora_ponta=dado[
                            'CreditosUtilizadosForaPonta'
                        ].strip(),
                        creditos_expirados_ponta=dado[
                            'CreditosExpiradosPonta'
                        ].strip(),
                        creditos_expirados_fora_ponta=dado[
                            'CreditosExpiradosForaPonta'
                        ].strip(),
                        saldo_mensal_ponta=dado['SaldoMensalPonta'].strip(),
                        saldo_mensal_fora_ponta=dado[
                            'SaldoMensalForaPonta'
                        ].strip(),
                        creditos_expirar_ponta=dado[
                            'CreditosExpirarPonta'
                        ].strip(),
                        creditos_expirar_fora_ponta=dado[
                            'CreditosExpirarForaPonta'
                        ].strip(),
                        mes_expiracao=mes_expiracao,
                        saldo_acumulado=None
                        if linha.empty
                        else linha['Saldo Acumulado (Fora Ponta)'].values[0],
                        # saldo_acumulado if (mes_referencia.month == mes_referencia_excel.month and mes_referencia.year == mes_referencia_excel.year) else None,
                        data_leitura_anterior=None
                        if linha.empty
                        else fuso.localize(
                            dt.strptime(
                                linha['Data de Leitura Anterior'].values[0],
                                '%d/%m/%Y',
                            )
                        ),
                    )
                    injecoes.append(injecao)
                    execucoes += ' injecoes_append '
                    # print(injecao)

                Injecao.objects.bulk_create(injecoes, ignore_conflicts=True)

                url_instalacao = f'https://servicosonline.cpfl.com.br/agencia-webapi/api/instalacao/{values["Instalacao"]}'

                response = requests.get(url_instalacao, headers=headers)

                values['NumeroContrato'] = response.json()['Contrato']

                # Aqui buscamos a tarifa
                instalacao_cpfl = values['Instalacao']
                data_referencia = first_day_of_month

                response = requests.post(
                    'https://servicosonline.cpfl.com.br/agencia-webapi/api/conta-facil/validar-situacao',
                    headers=headers,
                    json={
                        'Instalacao': instalacao_cpfl,
                        #'DataReferencia': data_referencia.strftime('%d/%m/%Y')
                    },
                )
                printl('status code conta facil', response.status_code)
                if (
                    response.status_code == 412
                ):   # TODO: Necessita revisão. Sem o primeiro acesso a conta facil ainda não funciona
                    response = requests.post(
                        'https://servicosonline.cpfl.com.br/agencia-webapi/api/conta-facil/log-primeiro-acesso',
                        headers=headers,
                        json={
                            'Instalacao': instalacao_cpfl,
                        },
                    )
                    response = requests.post(
                        'https://servicosonline.cpfl.com.br/agencia-webapi/api/conta-facil/validar-situacao',
                        headers=headers,
                        json={
                            'Instalacao': instalacao_cpfl,
                            'DataReferencia': data_referencia.strftime(
                                '%d/%m/%Y'
                            ),
                        },
                    )

                # Save para gravar a data da próxima leitura da concessionária
                proxima_leitura = response.json()['MesAtual']['Historico'][
                    'DataProximaLeitura'
                ]
                proxima_leitura = dt.strptime(proxima_leitura, '%d/%m/%Y')
                proxima_leitura = fuso.localize(proxima_leitura)
                
                # Se a data da próxima leitura para esta instalação não estiver no dicionário 'instalacoes'
                # ou se a nova data da próxima leitura for posterior à data atualmente armazenada,
                # atualize a data da próxima leitura para esta instalação
                if (
                    id_radio not in instalacoes
                    or instalacoes[id_radio] < proxima_leitura
                ):
                    instalacoes[id_radio] = proxima_leitura

                # Inicialize a variável tarifa atual
                tarifa_atual = 0

                # Inicialize contadores e somas
                cont_tu = cont_te = soma_tu = soma_te = 0
                # print(response.json())

                # Loop através da lista
                for preco in response.json()['MesAtual']['Precos']:
                    # Verifique as condições
                    if preco['Tarifa'] == '2':
                        if preco['Descricao'] == 'TU-Consumo':
                            # Adicione o TipoPreco à soma_tu (certifique-se de converter TipoPreco para float)
                            soma_tu += float(preco['TipoPreco'])
                            cont_tu += 1
                        elif preco['Descricao'] == 'TE-Consumo':
                            # Adicione o TipoPreco à soma_te (certifique-se de converter TipoPreco para float)
                            soma_te += float(preco['TipoPreco'])
                            cont_te += 1

                # Calcule a média e adicione à tarifa
                if cont_tu > 0:
                    tarifa_atual += soma_tu / cont_tu
                if cont_te > 0:
                    tarifa_atual += soma_te / cont_te

                # Inicialize a variável tarifa mes passado
                tarifa_mes_passado = 0

                # Inicialize contadores e somas
                cont_tu = cont_te = soma_tu = soma_te = 0
                # print(response.json())

                # Loop através da lista
                for preco in response.json()['MesAnterior']['Precos']:
                    # Verifique as condições
                    if preco['Tarifa'] == '2':
                        if preco['Descricao'] == 'TU-Consumo':
                            # Adicione o TipoPreco à soma_tu (certifique-se de converter TipoPreco para float)
                            soma_tu += float(preco['TipoPreco'])
                            cont_tu += 1
                        elif preco['Descricao'] == 'TE-Consumo':
                            # Adicione o TipoPreco à soma_te (certifique-se de converter TipoPreco para float)
                            soma_te += float(preco['TipoPreco'])
                            cont_te += 1

                # Calcule a média e adicione à tarifa
                if cont_tu > 0:
                    tarifa_mes_passado += soma_tu / cont_tu
                if cont_te > 0:
                    tarifa_mes_passado += soma_te / cont_te
                execucoes += ' tarifas '
                data_url = 'https://servicosonline.cpfl.com.br/agencia-webapi/api/historico-consumo/busca-graficos'

                json_data = {
                    'Instalacao': values['Instalacao'],
                    'CodigoClasse': '1',
                    'CodEmpresaSAP': values['CodEmpresaSAP'],
                    'NumeroContrato': values['NumeroContrato'],
                    'TipoGrafico': 'Todos',
                    'ParceiroNegocio': values['ParceiroNegocio'],
                }

                # Faz a requisição para obter os dados
                response = requests.post(
                    data_url, headers=headers, json=json_data
                )
                response.raise_for_status()  # Verifica se ocorreu algum erro na requisição

                # Obtém os dados da resposta
                dados = response.json()
                # print(f'#####################{codigo}####################', dados)
                # extrai os dados de consumo e faturamento
                consumo_data = [
                    d
                    for d in dados['Graficos']
                    if d['TipoGrafico'] == 'HistoricoConsumo'
                ][0]['Dados']
                faturamento_data = [
                    d
                    for d in dados['Graficos']
                    if d['TipoGrafico'] == 'HistoricoFaturamento'
                ][0]['Dados']

                # cria um dicionário para armazenar os dados de consumo por mês/ano
                consumo_dict = {}
                for item in consumo_data:
                    mes_ano = fuso.localize(
                        dt.strptime(
                            item['Categoria'].replace('*', ''), '%m/%Y'
                        )
                    )
                    consumo = float(item['Valor'])
                    consumo_dict[mes_ano] = consumo
                # itera sobre os dados de faturamento e cria objetos Consumo
                for item in faturamento_data:

                    mes_ano = fuso.localize(
                        dt.strptime(item['Categoria'], '%m/%Y')
                    )
                    valor = float(item['Valor'])
                    consumo = consumo_dict.get(mes_ano, 0)
                    printl(
                        'tarifa',
                        tarifa_atual,
                        'mes_ano',
                        item['Categoria'],
                        'fdom',
                        first_day_of_month.strftime('%m/%Y'),
                    )

                    if item['Categoria'] == first_day_of_month.strftime(
                        '%m/%Y'
                    ):
                        tarifa = tarifa_atual
                    elif item['Categoria'] == last_month.strftime('%m/%Y'):
                        tarifa = tarifa_mes_passado
                    else:
                        tarifa = None

                    Consumo.objects.update_or_create(
                        instalacao=instalacao,
                        mes_ano=mes_ano,
                        defaults={
                            'consumo': consumo,
                            'valor': valor,
                            'tarifa': tarifa,
                        },
                    )
                execucoes += ' consumo '
                driver.get(
                    'https://www.cpfl.com.br/agencia/area-cliente/selecionar-perfil-instalacao'
                )
                
            # Após verificar todas as instalações, obtenha a data mais próxima entre todas as instalações
            proxima_leitura_concessionaria = min(instalacoes.values())

            # Atualize a data da próxima leitura para o cliente
            cliente_info.proxima_leitura_concessionaria = proxima_leitura_concessionaria
            cliente_info.save()
            execucoes += ' final '
            driver.quit()

            #print(execucoes, ' -- final')
            break

        except TimeoutException:
            # Se ocorrer uma exceção TimeoutException, aguarde alguns segundos antes de tentar novamente
            #print(execucoes, ' -- timeout')
            sleep(10)
        except Exception as e:
            # Captura a exceção e imprime informações detalhadas no console
            #print(execucoes, ' -- exception')
            print(f'Erro: {e}')
            traceback.print_exc()
    else:
        driver.quit()
        # Se todas as tentativas falharem, levante uma exceção para indicar que o código falhou
        #print(execucoes, ' -- else')
        traceback.print_exc()
        raise Exception(
            #'Problema encontrado com a busca de dados. Um aviso foi enviado ao administrador (get_concessionaria_data)'
            execucoes
        )
