from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import get_object_or_404
from .models import MafiaGame

@admin.register(MafiaGame)
class MafiaGameAdmin(admin.ModelAdmin):
    list_display = ('code_short', 'host', 'stage', 'is_active', 'players_count', 'alive_count', 'mafia_count', 'created_at')
    list_filter = ('stage', 'is_active', 'created_at')
    search_fields = ('code', 'host__username', 'host__phone')
    readonly_fields = ('code', 'created_at')
    list_per_page = 20
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('code_short', 'host', 'stage', 'is_active', 'created_at')
        }),
        ('Статистика игры', {
            'fields': ('players_stats',),
            'classes': ('collapse',)
        }),
        ('Данные игроков', {
            'fields': ('players_data_display',),
            'classes': ('collapse',)
        }),
        ('Лог игры', {
            'fields': ('game_log_display',),
            'classes': ('collapse',)
        }),
        ('Текущие действия', {
            'fields': ('current_action',),
            'classes': ('collapse',)
        }),
    )
    
    def code_short(self, obj):
        return str(obj.code)[:8]
    code_short.short_description = 'Код игры'
    
    def players_count(self, obj):
        return len(obj.players_data)
    players_count.short_description = 'Всего игроков'
    
    def alive_count(self, obj):
        return len([p for p in obj.players_data if p.get('alive', True)])
    alive_count.short_description = 'Живых'
    
    def mafia_count(self, obj):
        alive = [p for p in obj.players_data if p.get('alive', True)]
        return len([p for p in alive if p.get('team') == 'mafia'])
    mafia_count.short_description = 'Мафия'
    
    def players_stats(self, obj):
        alive_players = [p for p in obj.players_data if p.get('alive', True)]
        dead_players = [p for p in obj.players_data if not p.get('alive', True)]
        
        mafia_alive = [p for p in alive_players if p.get('team') == 'mafia']
        civilian_alive = [p for p in alive_players if p.get('team') == 'civilian']
        neutral_alive = [p for p in alive_players if p.get('team') == 'neutral']
        
        stats_html = f'''
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="background: #e8f5e9; padding: 15px; border-radius: 12px;">
                <strong>❤️ Живые игроки:</strong> {len(alive_players)}<br>
                🔪 Мафия: {len(mafia_alive)}<br>
                👮 Мирные: {len(civilian_alive)}<br>
                🃏 Нейтральные: {len(neutral_alive)}
            </div>
            <div style="background: #ffebee; padding: 15px; border-radius: 12px;">
                <strong>💀 Мертвые игроки:</strong> {len(dead_players)}
            </div>
        </div>
        '''
        return stats_html
    players_stats.short_description = 'Статистика'
    
    def players_data_display(self, obj):
        if not obj.players_data:
            return "Нет данных"
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th>Имя</th><th>Роль</th><th>Команда</th><th>Статус</th></table>'
        
        for player in obj.players_data:
            status = '❤️ Жив' if player.get('alive', True) else '💀 Мертв'
            status_color = '#c8e6c9' if player.get('alive', True) else '#ffcdd2'
            team_color = '#ffeb3b' if player.get('team') == 'mafia' else ('#90caf9' if player.get('team') == 'civilian' else '#ce93d8')
            
            html += f'''
            <tr style="background: {status_color}; border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;">{player.get('icon', '👤')} {player.get('name', '?')}</td>
                <td style="padding: 8px;"><span style="background: {team_color}; padding: 2px 8px; border-radius: 12px;">{player.get('role_name', player.get('role', '?'))}</span></td>
                <td style="padding: 8px;">{player.get('team', '?')}</td>
                <td style="padding: 8px;">{status}</td>
            </tr>
            '''
        html += '</table>'
        return html
    players_data_display.short_description = 'Игроки'
    
    def game_log_display(self, obj):
        if not obj.game_log:
            return "Лог пуст"
        
        html = '<div style="max-height: 400px; overflow-y: auto; background: #f5f5f5; padding: 10px; border-radius: 8px;">'
        for log in obj.game_log[-20:]:
            html += f'<div style="padding: 5px; border-bottom: 1px solid #ddd; font-family: monospace;">[{log.get("time", "??")}] {log.get("message", "")}</div>'
        html += '</div>'
        return html
    game_log_display.short_description = 'Лог игры'
    
    # Кастомные действия
    actions = ['reset_selected_games', 'delete_selected_games']
    
    def reset_selected_games(self, request, queryset):
        """Сброс выбранных игр до начального состояния"""
        for game in queryset:
            game.stage = 'role_distribution'
            game.is_active = True
            game.current_action = {}
            # Воскрешаем всех игроков
            for player in game.players_data:
                player['alive'] = True
            game.game_log = []
            game.add_log('🔄 Игра была сброшена администратором')
            game.save()
        self.message_user(request, f'Сброшено {queryset.count()} игр')
    reset_selected_games.short_description = 'Сбросить выбранные игры'
    
    def delete_selected_games(self, request, queryset):
        count = queryset.delete()[0]
        self.message_user(request, f'Удалено {count} игр')
    delete_selected_games.short_description = 'Удалить выбранные игры'
    
    # Кастомные URL для админки
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reset-game/<uuid:game_code>/', self.admin_reset_game, name='reset_game'),
        ]
        return custom_urls + urls
    
    def admin_reset_game(self, request, game_code):
        game = get_object_or_404(MafiaGame, code=game_code)
        game.stage = 'role_distribution'
        game.is_active = True
        game.current_action = {}
        for player in game.players_data:
            player['alive'] = True
        game.game_log = []
        game.add_log('🔄 Игра была сброшена администратором')
        game.save()
        self.message_user(request, f'Игра {str(game.code)[:8]} сброшена')
        return HttpResponseRedirect('/admin/mafia/mafiagame/')
    
    # Убираем problematic метод get_actions, если он был
    # Вместо него используем actions = ['reset_selected_games', 'delete_selected_games']