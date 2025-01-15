class CPFouCNPJNaoEncontradoError(Exception):
    """
    Exceção personalizada para indicar que um CPF ou CNPJ não foi encontrado no banco de dados.

    Attributes:
        message (str): Mensagem de erro associada à exceção.

    Methods:
        __init__(self, message='CPF ou CNPJ não encontrados no banco de dados. Intervenção necessária.'):
            Inicializa a exceção com a mensagem fornecida ou a mensagem padrão, se não fornecida.

    Exemplo:
        ```
        try:
            raise CPFouCNPJNaoEncontradoError('Mensagem personalizada.')
        except CPFouCNPJNaoEncontradoError as e:
            print(f'Erro: {e}')
        ```
    """
    def __init__(
        self,
        message='CPF ou CNPJ não encontrados no banco de dados. Intervenção necessária.',
    ):
        """
        Inicializa a exceção com a mensagem fornecida ou a mensagem padrão, se não fornecida.

        Args:
            message (str, optional): Mensagem de erro personalizada. Padrão é a mensagem padrão da exceção.

        Returns:
            None
        """
        self.message = message
        super().__init__(self.message)


class TelNaoEncontradoError(Exception):
    """
    Exceção personalizada para indicar que o telefone não foi encontrado na tabela de credencial de concessionária.

    Attributes:
        message (str): Mensagem de erro associada à exceção.

    Methods:
        __init__(self, message='Telefone necessário e não encontrados no banco de dados. Intervenção necessária.'):
            Inicializa a exceção com a mensagem fornecida ou a mensagem padrão, se não fornecida.

    Exemplo:
        ```
        try:
            raise TelNaoEncontradoError('Mensagem personalizada.')
        except TelNaoEncontradoError as e:
            print(f'Erro: {e}')
        ```
    """
    def __init__(
        self,
        message='Telefone necessário e não encontrados no banco de dados. Intervenção necessária.',
    ):
        """
        Inicializa a exceção com a mensagem fornecida ou a mensagem padrão, se não fornecida.

        Args:
            message (str, optional): Mensagem de erro personalizada. Padrão é a mensagem padrão da exceção.

        Returns:
            None
        """
        self.message = message
        super().__init__(self.message)

class WaitingRoomException(Exception):
    pass

class BearerNotFound(Exception):
    pass
