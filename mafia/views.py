from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import MafiaGame
import json
import random


ROLES_CONFIG = {
    # Существующие роли
    'civilian': {'name': 'Мирный житель', 'team': 'civilian', 'icon': '👤', 'description': 'Голосуете днем, пытаетесь найти мафию', 'night_action': False},
    'mafia': {'name': 'Мафия', 'team': 'mafia', 'icon': '🔪', 'description': 'Ночью убиваете, днем притворяетесь', 'night_action': 'kill'},
    'don': {'name': 'Дон мафии', 'team': 'mafia', 'icon': '👑', 'description': 'Ночью проверяет, шериф ли игрок', 'night_action': 'check'},
    'sheriff': {'name': 'Шериф', 'team': 'civilian', 'icon': '🔍', 'description': 'Ночью проверяет, мафия ли игрок', 'night_action': 'check'},
    'doctor': {'name': 'Доктор', 'team': 'civilian', 'icon': '💊', 'description': 'Ночью лечит одного игрока', 'night_action': 'heal'},
    
    # НОВЫЕ РОЛИ
    'jester': {'name': 'Шут', 'team': 'neutral', 'icon': '🤡', 'description': 'Хочет, чтобы его выгнали днем. Если выгонят - накажет одного из голосовавших', 'night_action': False},
    'maniac': {'name': 'Маньяк', 'team': 'neutral', 'icon': '🥷🏻', 'description': 'Ночью убивает случайного игрока. Хочет остаться один', 'night_action': 'kill'},
    'bodyguard': {'name': 'Телохранитель', 'team': 'civilian', 'icon': '🛡️', 'description': 'Ночью защищает игрока. Если на защищаемого напали - погибает сам', 'night_action': 'protect'},
    'hooker': {'name': 'Путана', 'team': 'civilian', 'icon': '💄', 'description': 'Ночью "отключает" игрока - тот не может использовать способность', 'night_action': 'block'},
}

@login_required
def mafia_home(request):
    active_games = MafiaGame.objects.filter(host=request.user, is_active=True)
    return render(request, 'mafia/home.html', {'active_games': active_games})

@login_required
@require_http_methods(["POST"])
def create_game(request):
    try:
        data = json.loads(request.body)
        players = data.get('players', [])
        
        if len(players) < 4:
            return JsonResponse({'error': 'Минимум 4 игрока'}, status=400)
        
        for player in players:
            role_info = ROLES_CONFIG[player['role']]
            player.update({
                'alive': True,
                'icon': role_info['icon'],
                'team': role_info['team'],
                'role_name': role_info['name'],
                'role_description': role_info['description'],
            })
        
        game = MafiaGame.objects.create(
            host=request.user,
            players_data=players,
            stage='role_distribution'
        )
        
        game.add_log(f'🎮 Игра создана! Участников: {len(players)}')
        
        return JsonResponse({
            'success': True,
            'game_code': str(game.code),
            'redirect_url': f'/mafia/{game.code}/host/'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def host_game(request, game_code):
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    return render(request, 'mafia/host.html', {'game': game})

@login_required
def game_api(request, game_code):
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    # Добавьте отладку
    print(f"DEBUG API: game_log содержит {len(game.game_log)} записей")
    for log in game.game_log[-5:]:
        print(f"  {log['message']}")
    
    data = {
        'stage': game.stage,
        'stage_name': game.get_stage_display(),
        'players': game.players_data,
        'alive_players': game.get_alive_players(),
        'dead_players': game.get_dead_players(),
        'current_action': game.current_action,
        'game_log': game.game_log,  # Возвращаем ВСЕ логи, не только 10
        'is_game_over': game.stage == 'game_over',
        'mafia_count': len(game.get_mafia_players()),
        'civilian_count': len(game.get_alive_players()) - len(game.get_mafia_players()),
    }
    return JsonResponse(data)

# Обновите функцию process_action

@csrf_exempt
@login_required
@require_http_methods(["POST"])
def process_action(request, game_code):
    """Обработка действий ведущего"""
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    try:
        data = json.loads(request.body)
        action_type = data.get('action')
        target = data.get('target')
        
        print(f"DEBUG: process_action - action_type={action_type}, target={target}")
        
        # Все возможные действия
        valid_actions = [
            'mafia_target', 'sheriff_check', 'doctor_heal', 'don_check',
            'maniac_target', 'bodyguard_protect', 'hooker_block'
        ]
        
        if action_type in valid_actions:
            game.current_action[action_type] = target
            game.save()
            print(f"DEBUG: Сохранено {action_type} = {target}")
            
        elif action_type == 'day_vote_result':
            game.current_action['day_vote_result'] = target
            game.save()
            
        # НОВОЕ: сохранение голосов игроков
        elif action_type == 'day_vote':
            if 'day_votes' not in game.current_action:
                game.current_action['day_votes'] = {}
            game.current_action['day_votes'][target['voter']] = target['voted_for']
            game.save()
            print(f"DEBUG: Сохранен голос {target['voter']} -> {target['voted_for']}")
            
        else:
            return JsonResponse({'error': f'Unknown action: {action_type}'}, status=400)
        
        return JsonResponse({'success': True, 'action': action_type, 'target': target})
        
    except Exception as e:
        print(f"ERROR: {e}")
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@login_required
@require_http_methods(["POST"])
def next_stage_view(request, game_code):
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
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    try:
        player = game.players_data[player_index]
        return JsonResponse({
            'name': player['name'],
            'role': player['role_name'],
            'icon': player['icon'],
            'description': player.get('role_description', ''),
            'team': player['team'],
        })
    except IndexError:
        return JsonResponse({'error': 'Игрок не найден'}, status=404)

@login_required
@require_http_methods(["POST"])
def delete_game(request, game_code):
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    game.delete()
    return JsonResponse({'success': True})



@csrf_exempt
@login_required
@require_http_methods(["POST"])
def process_action(request, game_code):
    """Обработка действий ведущего"""
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    
    try:
        data = json.loads(request.body)
        action_type = data.get('action')
        target = data.get('target')
        
        print(f"DEBUG: process_action - action_type={action_type}, target={target}")
        
        # Все возможные действия
        valid_actions = [
            'mafia_target', 'sheriff_check', 'doctor_heal', 'don_check',
            'maniac_target', 'bodyguard_protect', 'hooker_block', 'jester_victim'
        ]
        
        if action_type in valid_actions:
            game.current_action[action_type] = target
            game.save()
            print(f"DEBUG: Сохранено {action_type} = {target}")
            
        elif action_type == 'day_vote_result':
            game.current_action['day_vote_result'] = target
            game.save()
            
        elif action_type == 'day_vote':
            if 'day_votes' not in game.current_action:
                game.current_action['day_votes'] = {}
            game.current_action['day_votes'][target['voter']] = target['voted_for']
            game.save()
            
        else:
            return JsonResponse({'error': f'Unknown action: {action_type}'}, status=400)
        
        return JsonResponse({'success': True, 'action': action_type, 'target': target})
        
    except Exception as e:
        print(f"ERROR: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    
    
@login_required
@require_http_methods(["POST"])
def delete_game(request, game_code):
    game = get_object_or_404(MafiaGame, code=game_code, host=request.user)
    game.delete()
    return JsonResponse({'success': True})