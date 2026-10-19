from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class MafiaGame(models.Model):
    STAGES = [
        ('setup', 'Настройка'),
        ('role_distribution', 'Раздача ролей'),
        ('night_processing', 'Ночь - Ввод действий'),  # Ведущий вводит действия
        ('night_results', 'Ночные результаты'),        # Показ результатов ночи
        ('day_discussion', 'Дневное обсуждение'),
        ('day_voting', 'Дневное голосование'),
        ('day_results', 'Результаты дня'),
        ('game_over', 'Игра окончена'),
    ]
    
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_mafia_games')
    players_data = models.JSONField(default=list)
    stage = models.CharField(max_length=30, choices=STAGES, default='setup')
    current_action = models.JSONField(default=dict, blank=True)
    game_log = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Игра Мафия'
        verbose_name_plural = 'Игры Мафия'

    def __str__(self):
        return f"Мафия {self.code} ({self.host})"
    
    def get_alive_players(self):
        return [p for p in self.players_data if p.get('alive', True)]
    
    def get_dead_players(self):
        return [p for p in self.players_data if not p.get('alive', True)]
    
    def get_mafia_players(self):
        return [p for p in self.get_alive_players() if p['team'] == 'mafia']
    
    def get_civilian_players(self):
        return [p for p in self.get_alive_players() if p['team'] == 'civilian']
    
    def kill_player(self, player_name):
        for p in self.players_data:
            if p['name'] == player_name and p.get('alive', True):
                p['alive'] = False
                self.save()
                return True
        return False
    
    def add_log(self, message):
        from django.utils import timezone
        self.game_log.append({
            'time': timezone.now().strftime('%H:%M:%S'),
            'message': message
        })
        if len(self.game_log) > 50:
            self.game_log = self.game_log[-50:]
        self.save()
    
    def check_game_end(self):
        """Проверка окончания игры"""
        alive = self.get_alive_players()
        mafia_alive = [p for p in alive if p['team'] == 'mafia']
        civilian_alive = [p for p in alive if p['team'] == 'civilian']
        
        if len(mafia_alive) == 0:
            self.stage = 'game_over'
            self.is_active = False
            self.add_log('🎉 ПОБЕДА МИРНЫХ ЖИТЕЛЕЙ! Вся мафия уничтожена! 🎉')
            self.save()
            return 'civilian'
            
        if len(mafia_alive) >= len(civilian_alive):
            self.stage = 'game_over'
            self.is_active = False
            self.add_log('🔪 ПОБЕДА МАФИИ! Мафия захватила город! 🔪')
            self.save()
            return 'mafia'
        
        return None