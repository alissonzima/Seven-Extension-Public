from apps.clientes.models import *
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm

# Modelos que aparecem para edição no painel de administração

admin.site.register(Cliente)
admin.site.register(Inversor)
admin.site.register(Empresa)
admin.site.register(CredencialInversor)
admin.site.register(Concessionaria)
admin.site.register(TipoUsuario)
admin.site.register(RelacaoClienteEmpresa)


from django.contrib import admin
from .models import CredencialConcessionaria, Cliente

class CredencialConcessionariaAdmin(admin.ModelAdmin):
    """
    Administração personalizada para o modelo CredencialConcessionaria.

    Esta classe define a personalização do admin para o modelo CredencialConcessionaria.
    Ela substitui o método `formfield_for_foreignkey` para personalizar a exibição do campo de cliente.

    Args:
        admin.ModelAdmin: Classe base do Django para personalização de administração.

    Métodos:
        formfield_for_foreignkey: Personaliza o campo de cliente para ser ordenado por nome da planta.
    """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Personaliza o campo de cliente para ser ordenado por nome da planta.

        Este método é chamado para personalizar a exibição do campo de cliente no admin.
        Ele substitui a queryset padrão para o campo de cliente, ordenando-a pelo nome da planta.

        Args:
            db_field (django.db.models.fields.related.ForeignKey): O campo de chave estrangeira.
            request (HttpRequest): O objeto de solicitação HTTP.
            **kwargs: Argumentos adicionais.

        Returns:
            Field: O campo personalizado.
        """
        if db_field.name == 'cliente':
            kwargs['queryset'] = Cliente.objects.order_by('plant_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# Registra a classe CredencialConcessionariaAdmin no admin
admin.site.register(CredencialConcessionaria, CredencialConcessionariaAdmin)


class UsuarioCustomizadoAdminForm(UserChangeForm):
    """
    Formulário de administração personalizado para o modelo UsuarioCustomizado.

    Este formulário é usado no painel de administração para editar instâncias do modelo UsuarioCustomizado.

    Args:
        UserChangeForm: Classe base para formulários de administração de alteração de usuário.

    Atributos:
        Meta: Subclasse que define metadados para o formulário.

    Meta:
        model (UsuarioCustomizado): O modelo associado ao formulário.

    """

    class Meta(UserChangeForm.Meta):
        model = UsuarioCustomizado


class UsuarioCustomizadoAdmin(UserAdmin):
    """
    Administração personalizada para o modelo UsuarioCustomizado.

    Esta classe define a personalização do admin para o modelo UsuarioCustomizado.
    Ela utiliza o formulário personalizado UsuarioCustomizadoAdminForm.

    Attributes:
        model (UsuarioCustomizado): O modelo associado à administração.
        list_display (list): Lista de campos a serem exibidos na lista de usuários no admin.
        form (UsuarioCustomizadoAdminForm): O formulário personalizado para edição.

    Fieldsets:
        Define agrupamentos de campos para melhor organização no painel de administração.

    Add Fieldsets:
        Define os campos adicionais necessários ao criar um novo usuário no admin.

    Métodos:
        Nenhum além dos métodos herdados de UserAdmin.

    """

    model = UsuarioCustomizado
    list_display = [
        'username',
        'email',
        'is_staff',
    ]
    form = UsuarioCustomizadoAdminForm  # Use o formulário personalizado para edição

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (
            'Informações Pessoais',
            {
                'fields': (
                    'first_name',
                    'last_name',
                    'email',
                    'tipo_usuario',
                    'cliente',
                    'empresa',
                )
            },
        ),
        (
            'Permissões',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'tipo_usuario',
                    'cliente',
                    'empresa',
                ),
            },
        ),
    )


admin.site.register(UsuarioCustomizado, UsuarioCustomizadoAdmin)
