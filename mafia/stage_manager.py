from .models import MafiaGame
import random


def execute_night_results(game):
    """Обработка всех ночных действий"""
    print(f"Обработка ночных результатов для игры {game.code}")
    
    # Проверяем, не закончилась ли уже игра
    if game.stage == 'game_over':
        return
    
    mafia_target = None
    doctor_heal = game.current_action.get('doctor_heal')
    sheriff_check = game.current_action.get('sheriff_check')
    don_check = game.current_action.get('don_check')
    
    # Определяем цель мафии
    mafia_votes = game.current_action.get('mafia_votes', {})
    if mafia_votes:
        vote_count = {}
        for voter, target in mafia_votes.items():
            if target:
                vote_count[target] = vote_count.get(target, 0) + 1
        
        if vote_count:
            mafia_target = max(vote_count, key=vote_count.get)
    
    # Определяем, кто убит
    if mafia_target:
        if mafia_target == doctor_heal and doctor_heal:
            game.add_log(f'💊 Доктор спас {mafia_target} от смерти этой ночью!')
        else:
            game.kill_player(mafia_target)
            game.add_log(f'🔪 Этой ночью был убит {mafia_target}')
    
    # Результаты проверки дона
    if don_check and has_role(game, 'don'):
        target_player = next((p for p in game.players_data if p['name'] == don_check), None)
        if target_player:
            if target_player['role'] == 'sheriff':
                game.add_log(f'👑 Дон мафии узнал: {don_check} - ШЕРИФ!')
            else:
                game.add_log(f'👑 Дон мафии узнал: {don_check} - не шериф')
    
    # Результаты проверки шерифа
    if sheriff_check and has_role(game, 'sheriff'):
        target_player = next((p for p in game.players_data if p['name'] == sheriff_check), None)
        if target_player:
            if target_player['team'] == 'mafia':
                game.add_log(f'🔍 Шериф узнал: {sheriff_check} - МАФИЯ!')
            else:
                game.add_log(f'🔍 Шериф узнал: {sheriff_check} - мирный житель')
    
    game.save()
    
    # Проверяем конец игры
    game.check_game_end()

def execute_day_voting(game):
    """Обработка дневного голосования"""
    print(f"Обработка дневного голосования для игры {game.code}")
    
    if game.stage == 'game_over':
        return
    
    day_votes = game.current_action.get('day_votes', {})
    
    if not day_votes:
        game.add_log('🤝 Сегодня никого не выгнали')
        game.save()
        return
    
    # Считаем голоса
    vote_count = {}
    for voter, target in day_votes.items():
        if target and target != 'воздержался':
            vote_count[target] = vote_count.get(target, 0) + 1
    
    if not vote_count:
        game.add_log('🤝 Сегодня никого не выгнали (все воздержались)')
    else:
        max_votes = max(vote_count.values())
        candidates = [name for name, count in vote_count.items() if count == max_votes]
        
        if len(candidates) > 1:
            game.add_log(f'⚖️ Равное количество голосов. Никто не выгнан.')
        else:
            voted_out = candidates[0]
            game.kill_player(voted_out)
            
            # Показываем роль
            player = next((p for p in game.players_data if p['name'] == voted_out), None)
            if player:
                if player['team'] == 'mafia':
                    game.add_log(f'🗳️ Город выгнал {voted_out}. Это был {player["role_name"]}! 🎯')
                else:
                    game.add_log(f'🗳️ Город выгнал {voted_out}. Это был {player["role_name"]} 😢')
    
    game.save()
    game.check_game_end()

def has_role(game, role):
    """Проверяет, есть ли роль среди живых игроков"""
    return any(p['role'] == role and p.get('alive', True) for p in game.players_data)

def next_stage(game):
    """Переход к следующей стадии"""
    print(f"Переход со стадии: {game.stage}")
    
    # Если игра окончена — не переходим
    if game.stage == 'game_over':
        print("Игра уже окончена")
        return
    
    # После раздачи ролей
    if game.stage == 'role_distribution':
        game.stage = 'night_mafia'
        game.add_log('🌙 Наступает ночь. Город засыпает.')
        game.current_action = {}
        game.save()
        return
    
    # После мафии
    if game.stage == 'night_mafia':
        if has_role(game, 'don'):
            game.stage = 'night_don'
        elif has_role(game, 'sheriff'):
            game.stage = 'night_sheriff'
        elif has_role(game, 'doctor'):
            game.stage = 'night_doctor'
        else:
            execute_night_results(game)
            game.stage = 'night_results'
        game.save()
        return
    
    # После дона
    if game.stage == 'night_don':
        if has_role(game, 'sheriff'):
            game.stage = 'night_sheriff'
        elif has_role(game, 'doctor'):
            game.stage = 'night_doctor'
        else:
            execute_night_results(game)
            game.stage = 'night_results'
        game.save()
        return
    
    # После шерифа
    if game.stage == 'night_sheriff':
        if has_role(game, 'doctor'):
            game.stage = 'night_doctor'
        else:
            execute_night_results(game)
            game.stage = 'night_results'
        game.save()
        return
    
    # После доктора
    if game.stage == 'night_doctor':
        execute_night_results(game)
        game.stage = 'night_results'
        game.current_action = {}
        game.save()
        return
    
    # После показа ночных результатов
    if game.stage == 'night_results':
        if game.stage != 'game_over':
            game.stage = 'day_intro'
            game.current_action = {}
            game.save()
        return
    
    # Дневные фазы
    if game.stage == 'day_intro':
        game.stage = 'day_speech'
        game.save()
        return
    
    if game.stage == 'day_speech':
        game.stage = 'day_voting'
        game.save()
        return
    
    # После голосования
    if game.stage == 'day_voting':
        execute_day_voting(game)
        game.stage = 'day_voting_results'
        game.current_action = {}
        game.save()
        return
    
    # После результатов дня
    if game.stage == 'day_voting_results':
        if game.stage != 'game_over':
            game.stage = 'night_mafia'
            game.current_action = {}
            game.add_log('🌙 Наступает ночь.')
            game.save()
        return