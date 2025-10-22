from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Room, Participant, SantaPair, Chat, Message

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['phone', 'first_name', 'is_staff', 'date_joined']
    search_fields = ['phone', 'first_name']
    ordering = ['phone']
    
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'password1', 'password2'),
        }),
    )

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'admin', 'created_at', 'is_active', 'draw_completed']
    list_filter = ['is_active', 'draw_completed', 'created_at']
    search_fields = ['name', 'code']
    actions = ['delete_selected_rooms']
    
    def delete_selected_rooms(self, request, queryset):
        """Кастомное действие для удаления комнат с очисткой связанных объектов"""
        for room in queryset:
            room.delete_room()
        self.message_user(request, f"Успешно удалено {queryset.count()} комнат")
    delete_selected_rooms.short_description = "Удалить выбранные комнаты (с очисткой)"

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'joined_at']
    list_filter = ['room', 'joined_at']

@admin.register(SantaPair)
class SantaPairAdmin(admin.ModelAdmin):
    list_display = ['room', 'santa', 'receiver']
    list_filter = ['room']

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ['room', 'user', 'participant', 'chat_type', 'created_at']
    list_filter = ['chat_type', 'room', 'created_at']
    search_fields = ['user__phone', 'participant__phone', 'room__name']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'participant', 'room')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'content', 'chat', 'timestamp', 'is_read']
    list_filter = ['timestamp', 'is_read']
    search_fields = ['content', 'sender__phone']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sender', 'chat')