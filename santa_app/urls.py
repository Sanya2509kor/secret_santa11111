from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('support/', views.support_page, name='support'),
    path('room/<int:room_id>/', views.room_detail, name='room_detail'),
    path('room/<int:room_id>/delete/', views.delete_room, name='delete_room'),
    path('room/<int:room_id>/draw/', views.start_draw, name='start_draw'),
    path('room/<int:room_id>/wishlist/', views.edit_wishlist, name='edit_wishlist'),
    path('room/<int:room_id>/wishlist/<int:participant_id>/', views.view_wishlist, name='view_wishlist'),
    path('chat/<int:chat_id>/', views.chat_detail, name='chat_detail'),
    path('chat/<int:chat_id>/messages/', views.get_messages, name='get_messages'),
    path('chat/<int:chat_id>/send/', views.send_message, name='send_message'),
    path('chat/<int:chat_id>/mark_read/', views.mark_messages_read, name='mark_messages_read'),
    path('get_user_chats/', views.get_user_chats, name='get_user_chats'),
    path('room/<int:room_id>/toggle_participants/', views.toggle_participants_visibility, name='toggle_participants'),
]