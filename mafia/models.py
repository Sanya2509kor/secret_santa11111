from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class MafiaGame(models.Model):
    STAGES = [
        ('setup', 'Настройка'),
        ('role_distribution', 'Раздача ролей'),
        ('night_mafia', 'Ночь - Мафия'),
        ('night_don', 'Ночь - Дон'),
        ('night_sheriff', 'Ночь - Шериф'),
        ('night_doctor', 'Ночь - Доктор'),
        ('day_intro', 'Объявление дня'),
        ('day_speech', 'Дневное обсуждение'),
        ('day_voting', 'Дневное голосование'),
        ('day_voting_results', 'Результаты голосования'),
        ('night_results', 'Ночные результаты'),
        ('game_over', 'Игра окончена'),
    ]
    
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_mafia_games')
    players_data = models.JSONField(default=list)
    stage = models.CharField(max_length=30, choices=STAGES, default='setup')
    current_action = models.JSONField(default=dict, blank=True)
    game_log = models.JSONField(default=list, blank=True)  # История событий
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Игра Мафия'
        verbose_name_plural = 'Игры Мафия'

    def __str__(self):
        return f"Мафия {self.code} ({self.host})"
    
    def get_alive_players(self):
        return [p for p in self.players_data if p.get('alive', True)]
    
    def get_players_by_role(self, role):
        return [p for p in self.get_alive_players() if p['role'] == role]
    
    def kill_player(self, player_name):
        for p in self.players_data:
            if p['name'] == player_name:
                p['alive'] = False
                self.save()
                return True
        return False
    
    def add_log(self, message):
        from django.utils import timezone
        self.game_log.append({
            'time': timezone.now().strftime('%H:%M'),
            'message': message
        })
        self.save()
    
    def check_game_end(self):
        """Проверка окончания игры"""
        alive = self.get_alive_players()
        mafia_alive = [p for p in alive if p['team'] == 'mafia']
        civilian_alive = [p for p in alive if p['team'] == 'civilian']
        
        print(f"Проверка конца игры: мафия={len(mafia_alive)}, мирные={len(civilian_alive)}")
        
        if not mafia_alive:
            self.stage = 'game_over'
            self.is_active = False
            self.add_log('🎉 Мирные жители победили! Вся мафия уничтожена.')
            self.save()
            return 'civilian'
            
        if len(mafia_alive) >= len(civilian_alive):
            self.stage = 'game_over'
            self.is_active = False
            self.add_log('🔪 Мафия захватила город! Мафия победила.')
            self.save()
            return 'mafia'
        
        return None