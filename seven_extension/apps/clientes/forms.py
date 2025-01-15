from apps.clientes.models import (
    Cliente,
    CredencialConcessionaria,
    CredencialInversor,
    UsuarioCustomizado,
)
from django import forms
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.forms import widgets


class UsuarioCustomizadoForm(forms.ModelForm):
    """
    Formulário para criar/editar um usuário personalizado.

    Attributes:
        Meta (class): Configurações do formulário, incluindo o modelo associado e os campos a serem exibidos.
        __init__ (method): Inicializa o formulário, permitindo a filtragem de clientes com base no cliente_id.
    """

    class Meta:
        """
        Configurações do formulário.

        Attributes:
            model (class): O modelo associado ao formulário.
            fields (list): Os campos do modelo a serem exibidos no formulário.
            widgets (dict): Configurações de widget para cada campo do formulário.
        """

        model = UsuarioCustomizado
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
        ]
        widgets = {
            'username': forms.TextInput(
                attrs={'class': 'form-control', 'readonly': True}
            ),
            'first_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite seu nome',
                }
            ),
            'last_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite seu sobrenome',
                }
            ),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        """
        Inicializa o formulário, permitindo a filtragem de clientes com base no cliente_id.

        Args:
        - cliente_id (int): O ID do cliente a ser filtrado.
        """
        cliente_id = kwargs.pop('cliente_id', None)
        super(UsuarioCustomizadoForm, self).__init__(*args, **kwargs)
        # if cliente_id:
        #     self.fields['cliente'].queryset = Cliente.objects.filter(id=cliente_id)


class CredencialConcessionariaForm(forms.ModelForm):
    """
    Formulário para criar/editar as credenciais da concessionária.

    Attributes:
        senha (CharField): Campo de senha com configurações específicas.
        geracao_projeto (CharField): Campo de geração do projeto com configurações específicas.
        Meta (class): Configurações do formulário, incluindo o modelo associado e os campos a serem exibidos.
        clean_senha (method): Validação do campo de senha.
        clean_geracao_projeto (method): Validação do campo de geração do projeto.
        __init__ (method): Inicializa o formulário, permitindo a filtragem de clientes com base no cliente_id.
    """

    senha = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Digite sua senha na concessionária',
                'autocomplete': 'off',
            }
        ),
        required=False,
    )
    geracao_projeto = forms.CharField(
        label='Geração do projeto',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        """
        Configurações do formulário.

        Attributes:
            model (class): O modelo associado ao formulário.
            fields (list): Os campos do modelo a serem exibidos no formulário.
            widgets (dict): Configurações de widget para cada campo do formulário.
        """

        model = CredencialConcessionaria
        fields = ['concessionaria', 'usuario', 'senha', 'cpf_cnpj']
        widgets = {
            'concessionaria': forms.Select(attrs={'class': 'form-control'}),
            'usuario': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite seu usuário na concessionária',
                    'autocomplete': 'off',
                }
            ),
            'cpf_cnpj': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite o CPF ou CNPJ associado à concessionária',
                }
            ),
        }

    def clean_senha(self):
        """
        Validação do campo de senha.

        Returns:
            senha (str): Senha válida.
        """
        senha = self.cleaned_data.get('senha')
        if not senha:
            # Retorna o valor atual da senha se o campo estiver vazio
            return self.instance.senha
        return senha

    def clean_geracao_projeto(self):
        """
        Validação do campo de geração do projeto.

        Returns:
            geracao_projeto (float): Geração do projeto válida.
        """
        geracao_projeto = self.cleaned_data.get('geracao_projeto')
        if geracao_projeto:
            # Substitua as vírgulas por pontos
            geracao_projeto = str(geracao_projeto).replace(',', '.')
            # Converta a string para float
            try:
                return float(geracao_projeto)
            except ValueError:
                raise forms.ValidationError(
                    'Por favor, insira um número válido.'
                )
        return geracao_projeto

    def __init__(self, *args, **kwargs):
        """
        Inicializa o formulário, permitindo a filtragem de clientes com base no cliente_id.

        Args:
            cliente_id (int): O ID do cliente a ser filtrado.
            user_type (str): O tipo de usuário para determinar a edição do campo de geração do projeto.
        """
        cliente_id = kwargs.pop('cliente_id', None)
        user_type = kwargs.pop('user_type', None)
        super(CredencialConcessionariaForm, self).__init__(*args, **kwargs)
        if user_type not in ['admin', 'integrador']:
            self.fields['geracao_projeto'].widget.attrs['readonly'] = True
        # if cliente_id:
        #     self.fields['cliente'].queryset = Cliente.objects.filter(id=cliente_id)


class CredencialInversorForm(forms.ModelForm):
    """
    Formulário para criar/editar as credenciais do inversor.

    Attributes:
        Meta (class): Configurações do formulário, incluindo o modelo associado e os campos a serem exibidos.
        __init__ (method): Inicializa o formulário, permitindo a filtragem de clientes com base no cliente_id.
    """

    class Meta:
        """
        Configurações do formulário.

        Attributes:
            model (class): O modelo associado ao formulário.
            fields (list): Os campos do modelo a serem exibidos no formulário.
            widgets (dict): Configurações de widget para cada campo do formulário.
        """

        model = CredencialInversor
        fields = ['inversor', 'usuario', 'senha']
        widgets = {
            'inversor': forms.Select(
                attrs={
                    'class': 'form-control',
                }
            ),
            'usuario': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite seu usuário',
                }
            ),
            'senha': forms.PasswordInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite sua senha',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        """
        Inicializa o formulário, permitindo a filtragem de clientes com base no cliente_id.

        Args:
                                        cliente_id (int): O ID do cliente a ser filtrado.
        """
        cliente_id = kwargs.pop('cliente_id', None)
        super(CredencialInversorForm, self).__init__(*args, **kwargs)
        # if cliente_id:
        #     self.fields['cliente'].queryset = Cliente.objects.filter(id=cliente_id)


class AtualizarSenhaForm(forms.Form):
    """
    Formulário para atualizar a senha do usuário.

    Attributes:
        old_password (CharField): Campo para a senha antiga.
        new_password1 (CharField): Campo para a nova senha.
        new_password2 (CharField): Campo para a confirmação da nova senha.
        __init__ (method): Inicializa o formulário com o usuário atual.
        clean_old_password (method): Valida se a senha antiga está correta.
        clean_new_password2 (method): Valida se as novas senhas coincidem.
        save (method): Salva a nova senha para o usuário.
    """

    old_password = forms.CharField(
        label='Senha antiga',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    new_password1 = forms.CharField(
        label='Nova senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    new_password2 = forms.CharField(
        label='Confirmação da nova senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, user, *args, **kwargs):
        """
        Inicializa o formulário com o usuário atual.

        Args:
            user (User): O usuário cuja senha será atualizada.
        """
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        """
        Valida se a senha antiga está correta.
        """
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('A senha antiga está incorreta.')
        return old_password

    def clean_new_password2(self):
        """
        Valida se as novas senhas coincidem.
        """
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('As senhas não coincidem.')
        return new_password2

    def save(self):
        """
        Salva a nova senha para o usuário.
        """
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        self.user.save()
        update_session_auth_hash(
            self.user
        )  # Atualiza a sessão do usuário para manter o login


class CriarUsuarioCustomizadoForm(forms.ModelForm):
    """
    Formulário para criar um novo usuário customizado.

    Attributes:
        senha (CharField): Campo para a senha do usuário.
        confirmar_senha (CharField): Campo para a confirmação da senha do usuário.
        clean (method): Valida se as senhas coincidem.
        save (method): Salva o novo usuário com a senha criptografada.
    """

    senha = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirmar_senha = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UsuarioCustomizado
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite o usuário',
                }
            ),
            'first_name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Digite o nome'}
            ),
            'last_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite o sobrenome',
                }
            ),
            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Digite o e-mail',
                }
            ),
        }

    def clean(self):
        """
        Valida se as senhas coincidem.
        """
        cleaned_data = super().clean()
        senha = cleaned_data.get('senha')
        confirmar_senha = cleaned_data.get('confirmar_senha')

        if senha and confirmar_senha and senha != confirmar_senha:
            self.add_error('confirmar_senha', 'As senhas não coincidem.')

    def save(self, commit=True):
        """
        Salva o novo usuário com a senha criptografada.

        Args:
            commit (bool): Indica se o objeto deve ser salvo no banco de dados.

        Returns:
            user (UsuarioCustomizado): O novo usuário criado.
        """
        user = super().save(commit=False)
        senha = self.cleaned_data['senha']
        user.set_password(senha)
        if commit:
            user.save()
        return user
