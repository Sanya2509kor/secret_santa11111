from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import MafiaGame
import json
import random

ROLES_CONFIG = {
    'civilian': {'name': 'Мирный житель', 'team': 'civilian', 'icon': '👤'},
    'mafia': {'name': 'Мафия', 'team': 'mafia', 'icon': '🔪'},
    'don': {'name': 'Дон мафии', 'team': 'mafia', 'icon': '👑'},
    'sheriff': {'name': 'Шериф', 'team': 'civilian', 'icon': '🔍'},
    'doctor': {'name': 'Доктор', 'team': 'civilian', 'icon': '💊'},
}

@login_required
def mafia_home(request):
    """Главная страница Мафии"""
    active_games = MafiaGame.objects.filter(host=request.user, is_active=True)
    return render(request, 'mafia/home.html', {'active_games': active_games})

@login_required
def create_game(request):
    """Создание новой игры"""
    if request.method == 'POST':
        data = json.loads(request.body)
        players = data.get('players', [])
        
        # Перемешиваем роли
        random.shuffle(players)
        
        # Добавляем информацию о ролях
        for player in players:
            role_info = ROLES_CONFIG[player['role']]
            player.update({
                'alive': True,
                'icon': role_info['icon'],
                'team': role_info['team'],
                'role_name': role_info['name'],
            })
        
        game = MafiaGame.objects.create(
            host=request.user,
            players_data=players,
            stage='role_distribution'
        )
        
        return JsonResponse({
            'success': True,
            'game_code': str(game.code),
            'redirect_url': f'/mafia/{game.code}/host/'  # Проверьте этот путь
        })
    
    return JsonResponse({'error': 'POST required'})

@login_required
def host_game(request, game_code):
    """Экран ведущего"""
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    context = {
        'game': game,
        'stages': dict(MafiaGame.STAGES),
    }
    return render(request, 'mafia/host.html', context)

@login_required
def game_api(request, game_code):
    """API для получения состояния игры"""
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    data = {
        'stage': game.stage,
        'stage_name': game.get_stage_display(),
        'players': game.players_data,
        'alive_players': game.get_alive_players(),
        'current_action': game.current_action,
        'game_log': game.game_log[-8:],  # Последние 8 событий
        'is_game_over': game.stage == 'game_over',
    }
    
    return JsonResponse(data)

@csrf_exempt
@login_required
def process_action(request, game_code):
    """Обработка действий (выбор цели)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'})
    
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    data = json.loads(request.body)
    
    action_type = data.get('action')  # mafia_kill, sheriff_check, doctor_heal, don_check, day_vote
    target = data.get('target')
    actor = data.get('actor', '')
    
    if action_type == 'mafia_kill':
        # Сохраняем выбор мафии
        if 'mafia_votes' not in game.current_action:
            game.current_action['mafia_votes'] = {}
        game.current_action['mafia_votes'][actor] = target
        game.save()
        
    elif action_type == 'sheriff_check':
        # Шериф проверяет игрока
        game.current_action['sheriff_check'] = target
        game.save()
        
    elif action_type == 'doctor_heal':
        # Доктор лечит
        game.current_action['doctor_heal'] = target
        game.save()
        
    elif action_type == 'don_check':
        # Дон проверяет шерифа
        game.current_action['don_check'] = target
        game.save()
        
    elif action_type == 'day_vote':
        # Дневное голосование
        if 'day_votes' not in game.current_action:
            game.current_action['day_votes'] = {}
        game.current_action['day_votes'][actor] = target
        game.save()
    
    return JsonResponse({'success': True})


# Добавьте в mafia/views.py новые функции

@csrf_exempt
@login_required
def next_stage_view(request, game_code):
    """Переход к следующей стадии"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'})
    
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    from .stage_manager import next_stage
    next_stage(game)
    
    return JsonResponse({
        'success': True,
        'new_stage': game.stage,
        'stage_name': game.get_stage_display(),
    })

@login_required
def show_role(request, game_code, player_index):
    """Показать роль игрока (для фазы раздачи)"""
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    try:
        player = game.players_data[player_index]
        return JsonResponse({
            'name': player['name'],
            'role': player['role_name'],
            'icon': player['icon'],
        })
    except IndexError:
        return JsonResponse({'error': 'Игрок не найден'})

@login_required
def delete_game(request, game_code):
    """Удаление игры"""
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    if request.method == 'POST':
        game.delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'POST required'})