from django.urls import path
from . import views

urlpatterns = [
    path('', views.mafia_home, name='mafia_home'),
    path('create/', views.create_game, name='mafia_create'),
    path('<uuid:game_code>/host/', views.host_game, name='mafia_host'),
    path('<uuid:game_code>/api/', views.game_api, name='mafia_api'),
    path('<uuid:game_code>/action/', views.process_action, name='mafia_action'),
    path('<uuid:game_code>/next-stage/', views.next_stage_view, name='mafia_next_stage'),
    path('<uuid:game_code>/role/<int:player_index>/', views.show_role, name='mafia_show_role'),
    path('<uuid:game_code>/delete/', views.delete_game, name='mafia_delete'),
]