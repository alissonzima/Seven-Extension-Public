from apps.clientes import views
from django.urls import path

urlpatterns = [
    #path('', views.index, name='index'),
    path('atualizar_tab', views.atualizar_tab, name='atualizar_tab'),
    # path('csrf', views.csrf, name='csrf'),
    # path('consumo', views.busca_consumo, name='busca_consumo'),
    # path('listar', views.listar_clientes, name='listar_clientes'),
    # path('geracao', views.geracao_clientes, name='geracao_clientes'),
    path('profile_user', views.profile_user, name='profile_user'),
    path('notificacao', views.notificacao, name='notificacao'),
]
