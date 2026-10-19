from .models import MafiaGame
import random

def process_mafia_vote(game):
    """Обработка голосования мафии"""
    mafia_target = game.current_action.get('mafia_target')
    print(f"DEBUG: process_mafia_vote - mafia_target={mafia_target}")
    
    # Если цель не выбрана или пустая - мафия никого не убивает
    if not mafia_target or mafia_target == '' or mafia_target == 'никого':
        game.add_log('🤝 Мафия решила никого не убивать этой ночью')
        game.save()
        return
    
    doctor_heal = game.current_action.get('doctor_heal')
    bodyguard_protect = game.current_action.get('bodyguard_protect')
    hooker_block = game.current_action.get('hooker_block')
    
    # Проверяем блокировку мафии
    mafia_blocked = False
    if hooker_block and hooker_block != '':
        mafia_players = [p['name'] for p in game.get_alive_players() if p['team'] == 'mafia']
        if hooker_block in mafia_players:
            mafia_blocked = True
            game.add_log(f'💄 Путана отключила мафию! Они не могут убить этой ночью')
    
    if mafia_blocked:
        game.add_log('🤝 Мафия не смогла убить (заблокирована)')
        game.save()
        return
    
    # Проверка: Доктор спас?
    if doctor_heal and doctor_heal != '' and mafia_target == doctor_heal:
        game.add_log(f'💊 Доктор спас {mafia_target} от смерти!')
        game.save()
        return
    
    # Проверка: Телохранитель защищает?
    if bodyguard_protect and bodyguard_protect != '' and mafia_target == bodyguard_protect:
        bodyguard_player = None
        for p in game.players_data:
            if p['role'] == 'bodyguard' and p.get('alive', True):
                bodyguard_player = p['name']
                break
        
        if bodyguard_player:
            game.kill_player(bodyguard_player)
            game.add_log(f'🛡️ Телохранитель {bodyguard_player} погиб, защищая {mafia_target}!')
            game.add_log(f'💀 Мафия целилась в {mafia_target}, но телохранитель принял удар')
            game.save()
            return
    
    # Если никто не спас и не защитил - убиваем цель
    game.kill_player(mafia_target)
    game.add_log(f'💀 Мафия убила {mafia_target}')
    game.save()


def process_maniac_kill(game):
    """Обработка убийства маньяком"""
    maniac_target = game.current_action.get('maniac_target')
    print(f"DEBUG: process_maniac_kill - maniac_target={maniac_target}")
    
    # Если цель не выбрана или пустая - маньяк никого не убивает
    if not maniac_target or maniac_target == '' or maniac_target == 'никого':
        game.add_log('🔪 Маньяк решил никого не убивать этой ночью')
        game.save()
        return
    
    hooker_block = game.current_action.get('hooker_block')
    doctor_heal = game.current_action.get('doctor_heal')
    bodyguard_protect = game.current_action.get('bodyguard_protect')
    
    # Проверяем блокировку маньяка
    maniac_players = [p['name'] for p in game.get_alive_players() if p['role'] == 'maniac']
    if hooker_block and hooker_block != '' and hooker_block in maniac_players:
        game.add_log(f'💄 Путана отключила маньяка! Он не может убить этой ночью')
        game.save()
        return
    
    # Проверка: Доктор спас?
    if doctor_heal and doctor_heal != '' and maniac_target == doctor_heal:
        game.add_log(f'💊 Доктор спас {maniac_target} от маньяка!')
        game.save()
        return
    
    # Проверка: Телохранитель защищает?
    if bodyguard_protect and bodyguard_protect != '' and maniac_target == bodyguard_protect:
        bodyguard_player = None
        for p in game.players_data:
            if p['role'] == 'bodyguard' and p.get('alive', True):
                bodyguard_player = p['name']
                break
        
        if bodyguard_player:
            game.kill_player(bodyguard_player)
            game.add_log(f'🛡️ Телохранитель {bodyguard_player} погиб, защищая {maniac_target} от маньяка!')
            game.save()
            return
    
    # Убиваем цель
    game.kill_player(maniac_target)
    game.add_log(f'🔪 Маньяк убил {maniac_target}!')
    game.save()


def process_sheriff_check(game):
    """Обработка проверки шерифа"""
    sheriff_check = game.current_action.get('sheriff_check')
    
    # Если цель не выбрана - шериф никого не проверяет
    if not sheriff_check or sheriff_check == '' or sheriff_check == 'никого':
        game.add_log('🔍 Шериф решил никого не проверять этой ночью')
        game.save()
        return
    
    hooker_block = game.current_action.get('hooker_block')
    sheriff_players = [p['name'] for p in game.get_alive_players() if p['role'] == 'sheriff']
    if hooker_block and hooker_block != '' and hooker_block in sheriff_players:
        game.add_log(f'💄 Путана отключила шерифа! Он не может проверить')
        game.save()
        return
    
    target_player = next((p for p in game.players_data if p['name'] == sheriff_check), None)
    if target_player and target_player.get('alive', True):
        if target_player['team'] == 'mafia':
            game.add_log(f'🔍 Шериф проверил {sheriff_check} - это МАФИЯ!')
        else:
            game.add_log(f'🔍 Шериф проверил {sheriff_check} - мирный житель')
    
    game.save()


def process_don_check(game):
    """Обработка проверки дона"""
    don_check = game.current_action.get('don_check')
    
    # Если цель не выбрана - дон никого не проверяет
    if not don_check or don_check == '' or don_check == 'никого':
        game.add_log('👑 Дон решил никого не проверять этой ночью')
        game.save()
        return
    
    hooker_block = game.current_action.get('hooker_block')
    don_players = [p['name'] for p in game.get_alive_players() if p['role'] == 'don']
    if hooker_block and hooker_block != '' and hooker_block in don_players:
        game.add_log(f'💄 Путана отключила дона! Он не может проверить')
        game.save()
        return
    
    target_player = next((p for p in game.players_data if p['name'] == don_check), None)
    if target_player and target_player.get('alive', True):
        if target_player['role'] == 'sheriff':
            game.add_log(f'👑 Дон узнал: {don_check} - ШЕРИФ!')
        else:
            game.add_log(f'👑 Дон узнал: {don_check} - не шериф')
    
    game.save()


def process_doctor_heal(game):
    """Обработка лечения доктора"""
    doctor_heal = game.current_action.get('doctor_heal')
    
    # Если цель не выбрана - доктор никого не лечит
    if not doctor_heal or doctor_heal == '' or doctor_heal == 'никого':
        game.add_log('💊 Доктор решил никого не лечить этой ночью')
    else:
        hooker_block = game.current_action.get('hooker_block')
        doctor_players = [p['name'] for p in game.get_alive_players() if p['role'] == 'doctor']
        if hooker_block and hooker_block != '' and hooker_block in doctor_players:
            game.add_log(f'💄 Путана отключила доктора! Он не может лечить')
        else:
            game.add_log(f'💊 Доктор лечит {doctor_heal}')
    
    game.save()


def process_bodyguard_protect(game):
    """Обработка защиты телохранителя"""
    bodyguard_protect = game.current_action.get('bodyguard_protect')
    
    if bodyguard_protect and bodyguard_protect != 'никого':
        hooker_block = game.current_action.get('hooker_block')
        
        # Проверяем, не заблокирован ли телохранитель
        bodyguard_players = [p['name'] for p in game.get_alive_players() if p['role'] == 'bodyguard']
        if hooker_block and hooker_block in bodyguard_players:
            game.add_log(f'💄 Путана отключила телохранителя! Он не может защитить этой ночью')
            return
        
        game.current_action['bodyguard_protect_active'] = bodyguard_protect
        game.add_log(f'🛡️ Телохранитель защищает {bodyguard_protect}')
    
    game.save()


def process_hooker_block(game):
    """Обработка блокировки путаны"""
    hooker_block = game.current_action.get('hooker_block')
    
    if hooker_block and hooker_block != 'никого':
        game.add_log(f'💄 Путана отключила {hooker_block} на эту ночь')
    
    game.save()


def execute_night_results(game):
    """Обработка всех ночных действий"""
    print(f"Обработка ночных результатов для игры {game.code}")
    print(f"DEBUG: current_action = {game.current_action}")
    
    if game.stage == 'game_over':
        return
    
    # Сохраняем состояние шерифа ДО ночных действий
    sheriff_alive_before = has_role(game, 'sheriff')
    
    # 1. Путана (блокирует)
    if has_role(game, 'hooker'):
        process_hooker_block(game)
    
    # 2. Проверка дона (если шериф жив)
    if has_role(game, 'don') and sheriff_alive_before:
        process_don_check(game)
    elif has_role(game, 'don') and not sheriff_alive_before:
        game.add_log('👑 Шериф мертв, дон мафии не может никого проверять этой ночью')
    
    # 3. Проверка шерифа (если жив)
    if has_role(game, 'sheriff'):
        process_sheriff_check(game)
    
    # 4. Лечение доктора
    if has_role(game, 'doctor'):
        process_doctor_heal(game)
    
    # 5. Защита телохранителя
    if has_role(game, 'bodyguard'):
        process_bodyguard_protect(game)
    
    # 6. Убийство мафии
    if has_role(game, 'mafia') or has_role(game, 'don'):
        process_mafia_vote(game)
        game.save()
    
    # 7. Убийство маньяка
    if has_role(game, 'maniac'):
        process_maniac_kill(game)
        game.save()
    
    game.check_game_end()


def execute_day_voting(game):
    """Обработка дневного голосования с учетом Шута"""
    print(f"Обработка дневного голосования для игры {game.code}")
    
    if game.stage == 'game_over':
        return
    
    voted_out = game.current_action.get('day_vote_result')
    jester_victim = game.current_action.get('jester_victim')
    print(f"DEBUG: day_vote_result = {voted_out}")
    print(f"DEBUG: jester_victim = {jester_victim}")
    
    if not voted_out or voted_out == 'никого':
        game.add_log('🤝 Город решил никого не выгонять')
        game.save()
        return
    
    alive_players_names = [p['name'] for p in game.get_alive_players()]
    
    if voted_out in alive_players_names:
        player = next((p for p in game.players_data if p['name'] == voted_out), None)
        
        # ПРОВЕРКА: ЭТО ШУТ?
        if player and player['role'] == 'jester':
            # Шут выгнан!
            game.kill_player(voted_out)
            game.add_log(f'🤡 Город выгнал {voted_out}. Это был ШУТ!')
            
            # Шут убивает выбранную жертву
            if jester_victim and jester_victim != 'никого' and jester_victim in alive_players_names:
                game.kill_player(jester_victim)
                victim_player = next((p for p in game.players_data if p['name'] == jester_victim), None)
                
                if victim_player:
                    game.add_log(f'😈 В предсмертной шутке, {voted_out} забирает с собой {jester_victim} ({victim_player["role_name"]})!')
                else:
                    game.add_log(f'😈 В предсмертной шутке, {voted_out} забирает с собой {jester_victim}!')
                
                game.add_log(f'🎉 Шут победил! Он хотел быть выгнанным и добился этого!')
            else:
                game.add_log(f'😔 Шут никого не забрал с собой...')
            
            game.save()
            game.check_game_end()
            return
        
        # Обычный игрок (не шут)
        game.kill_player(voted_out)
        if player['team'] == 'mafia':
            game.add_log(f'🗳️ Город выгнал {voted_out}. Это была МАФИЯ! 🎯')
        elif player['team'] == 'neutral':
            game.add_log(f'🗳️ Город выгнал {voted_out}. Это был нейтральный игрок')
        else:
            game.add_log(f'🗳️ Город выгнал {voted_out}. Это был мирный житель 😢')
    
    else:
        game.add_log(f'⚠️ {voted_out} уже мертв или не в игре')
    
    game.save()
    game.check_game_end()


def has_role(game, role):
    """Проверяет, есть ли роль среди живых игроков"""
    return any(p['role'] == role and p.get('alive', True) for p in game.players_data)


def next_stage(game):
    """Переход к следующей стадии"""
    print(f"Переход со стадии: {game.stage}")
    
    if game.stage == 'game_over':
        return
    
    stages_order = {
        'setup': 'role_distribution',
        'role_distribution': 'night_processing',
        'night_processing': 'night_results',
        'night_results': 'day_discussion',
        'day_discussion': 'day_voting',
        'day_voting': 'day_results',
        'day_results': 'night_processing',
    }
    
    if game.stage == 'night_processing':
        execute_night_results(game)
    
    if game.stage == 'day_voting':
        execute_day_voting(game)
    
    if game.stage == 'game_over':
        return
    
    next_stage_name = stages_order.get(game.stage)
    if next_stage_name:
        game.stage = next_stage_name
        game.current_action = {}
        
        alive_players = game.get_alive_players()
        alive_count = len(alive_players)
        mafia_count = len([p for p in alive_players if p['team'] == 'mafia'])
        civilian_count = len([p for p in alive_players if p['team'] == 'civilian'])
        neutral_count = len([p for p in alive_players if p['team'] == 'neutral'])
        
        if game.stage == 'night_processing':
            game.add_log(f'🌙 Ночь. Жителей: {alive_count} (мирных: {civilian_count}, мафия: {mafia_count}, нейтральных: {neutral_count})')
        elif game.stage == 'night_results':
            game.add_log('🌅 Рассвет...')
        elif game.stage == 'day_discussion':
            game.add_log(f'☀️ Доброе утро! В городе {alive_count} жителей.')
        elif game.stage == 'day_voting':
            game.add_log('🗳️ Начинается голосование!')
        elif game.stage == 'day_results':
            game.add_log('📊 Подведение итогов...')
        
        game.save()
        
        
def process_bodyguard_protect(game):
    """Обработка защиты телохранителя (только запись в лог)"""
    bodyguard_protect = game.current_action.get('bodyguard_protect')
    
    if bodyguard_protect and bodyguard_protect != 'никого':
        hooker_block = game.current_action.get('hooker_block')
        
        # Проверяем, не заблокирован ли телохранитель
        bodyguard_players = [p['name'] for p in game.get_alive_players() if p['role'] == 'bodyguard']
        if hooker_block and hooker_block in bodyguard_players:
            game.add_log(f'💄 Путана отключила телохранителя! Он не может защитить')
            return
        
        # Находим имя телохранителя
        bodyguard_name = None
        for p in game.players_data:
            if p['role'] == 'bodyguard' and p.get('alive', True):
                bodyguard_name = p['name']
                break
        
        if bodyguard_name:
            game.add_log(f'🛡️ Телохранитель {bodyguard_name} защищает {bodyguard_protect}')
            # Сохраняем в current_action для использования при убийстве
            game.current_action['bodyguard_protect_target'] = bodyguard_protect
            game.current_action['bodyguard_protect_player'] = bodyguard_name
    
    game.save()