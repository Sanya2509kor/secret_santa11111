from django.contrib import messages
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
import random
from .models import Room, Participant, SantaPair, Chat, Message, SupportMessage, User
from .forms import ParticipantNameForm, PasswordResetForm, PasswordResetRequestForm, PhoneUserCreationForm, PhoneAuthenticationForm, RoomForm, JoinRoomForm, MessageForm, SecurityAnswerForm, SecurityQuestionSetupForm, WishlistForm
from django.core.files.storage import FileSystemStorage
import os
from datetime import datetime, timedelta
import secrets
from django.utils import timezone
from datetime import timedelta
from .models import PasswordResetToken
from .forms import SECURITY_QUESTIONS

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        form = PhoneUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.phone  # Используем телефон как username
            user.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = PhoneUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = PhoneAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.get_display_name()}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Неверный номер телефона или пароль. Попробуйте еще раз.')
    else:
        form = PhoneAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, f'До скорой встречи!')
    return redirect('home')

@login_required
def dashboard(request):
    user_rooms = Room.objects.filter(participant__user=request.user)
    created_rooms = Room.objects.filter(admin=request.user)
    
    room_form = RoomForm()
    join_form = JoinRoomForm()
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'create_room':
            room_form = RoomForm(request.POST)
            
            if room_form.is_valid():
                room = room_form.save(commit=False)
                room.admin = request.user
                room.save()
                
                # Запрашиваем имя для создателя комнаты
                display_name = request.POST.get('display_name', '').strip()
                if not display_name:
                    # Если имя не указано, используем имя пользователя
                    display_name = request.user.get_display_name()
                
                # Создаем участника с указанным именем
                Participant.objects.create(
                    user=request.user, 
                    room=room, 
                    display_name=display_name
                )
                return redirect('room_detail', room_id=room.id)
                
        elif form_type == 'join_room':
            join_form = JoinRoomForm(request.POST)
            
            if join_form.is_valid():
                code = join_form.cleaned_data['code'].upper()
                try:
                    room = Room.objects.get(code=code, is_active=True)
                    
                    # Проверяем, не присоединен ли уже пользователь
                    if Participant.objects.filter(user=request.user, room=room).exists():
                        messages.info(request, 'Вы уже присоединены к этой комнате')
                        return redirect('room_detail', room_id=room.id)
                    
                    # Запрашиваем имя для нового участника
                    display_name = request.POST.get('display_name', '').strip()
                    if not display_name:
                        # Если имя не указано, используем имя пользователя
                        display_name = request.user.get_display_name()
                    
                    # Создаем участника с указанным именем
                    Participant.objects.create(
                        user=request.user, 
                        room=room, 
                        display_name=display_name
                    )
                    messages.success(request, f'Вы успешно присоединились к комнате как "{display_name}"')
                    return redirect('room_detail', room_id=room.id)
                    
                except Room.DoesNotExist:
                    join_form.add_error('code', 'Комната с таким кодом не найдена')
    
    return render(request, 'dashboard.html', {
        'user_rooms': user_rooms,
        'created_rooms': created_rooms,
        'room_form': room_form,
        'join_form': join_form,
    })

@login_required
def room_detail(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    participant = get_object_or_404(Participant, user=request.user, room=room)
    participants = Participant.objects.filter(room=room).order_by('?')

    # Форма для изменения имени в комнате
    name_form = ParticipantNameForm(instance=participant)

    # Получаем информацию о Санте и получателе
    my_santa = None
    my_receiver = None
    my_receiver_wishlist = None
    
    if room.draw_completed:
        # Кто мой Санта (кто мне дарит)
        my_santa_pair = SantaPair.objects.filter(room=room, receiver=request.user).first()
        if my_santa_pair:
            my_santa = my_santa_pair.santa
        
        # Кто мой получатель (кому я дарю)
        my_receiver_pair = SantaPair.objects.filter(room=room, santa=request.user).first()
        if my_receiver_pair:
            my_receiver = my_receiver_pair.receiver
            # Получаем пожелания получателя
            my_receiver_wishlist = Participant.objects.filter(
                user=my_receiver, 
                room=room
            ).first()
    
    # Получаем чаты пользователя
    user_chats = Chat.objects.filter(user=request.user, room=room)
    
    context = {
        'room': room,
        'participant': participant,
        'participants': participants,
        'my_santa': my_santa,
        'my_receiver': my_receiver_wishlist,
        'my_receiver_wishlist': my_receiver_wishlist,
        'user_chats': user_chats,
    }
    
    return render(request, 'room_detail.html', context)

@login_required
def edit_wishlist(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    participant = get_object_or_404(Participant, user=request.user, room=room)
    
    if request.method == 'POST':
        form = WishlistForm(request.POST, instance=participant)
        if form.is_valid():
            form.save()
            return redirect('room_detail', room_id=room.id)
    else:
        form = WishlistForm(instance=participant)
    
    return render(request, 'edit_wishlist.html', {
        'form': form,
        'room': room,
        'participant': participant,
    })

@login_required
def view_wishlist(request, room_id, participant_id=None):
    room = get_object_or_404(Room, id=room_id)
    
    if participant_id:
        # Просмотр пожеланий конкретного участника (для Санты)
        participant = get_object_or_404(Participant, id=participant_id, room=room)
        # Проверяем, что текущий пользователь - Санта для этого участника
        santa_pair = get_object_or_404(SantaPair, room=room, santa=request.user, receiver=participant.user)
    else:
        # Просмотр собственных пожеланий
        participant = get_object_or_404(Participant, user=request.user, room=room)
    
    return render(request, 'view_wishlist.html', {
        'room': room,
        'participant': participant,
        'is_own_wishlist': not participant_id,
    })



@login_required
def start_draw(request, room_id):
    room = get_object_or_404(Room, id=room_id, admin=request.user)
    
    if room.draw_completed:
        return redirect('room_detail', room_id=room.id)
    
    participants = list(Participant.objects.filter(room=room))
    users = [p.user for p in participants]
    
    if len(users) < 2:
        return redirect('room_detail', room_id=room.id)
    
    # Определяем специальные номера
    SPECIAL_PHONE = '79232967357'
    RESTRICTED_PHONES = {'89135503550', '89041500093', '89082117391', '89964272671', '89832814588'}
    a = '+79526136205'
    b = '89950775610'

    def is_valid_distribution(users_list):
        """Проверяет, что RESTRICTED_PHONES не дарит SPECIAL_PHONE"""
        for i in range(len(users_list)):
            santa = users_list[i]
            receiver = users_list[(i + 1) % len(users_list)]
            
            # Если специальный номер - Санта, проверяем получателя
            if receiver.phone == SPECIAL_PHONE and santa.phone in RESTRICTED_PHONES:
                return False
            if receiver.phone == a and santa.phone == b:
                return False
        return True

    # Перемешиваем до тех пор, пока не получим валидное распределение
    max_attempts = 100
    attempt = 0

    while attempt < max_attempts:
        random.shuffle(users)
        if is_valid_distribution(users):
            break
        attempt += 1
    else:
        # Если не удалось найти валидное распределение после всех попыток
        messages.warning(request, 'Не удалось создать идеальное распределение, но жеребьевка проведена')

    
    # Создаем пары Санта-Получатель
    for i in range(len(users)):
        santa = users[i]
        receiver = users[(i + 1) % len(users)]
        
        SantaPair.objects.create(room=room, santa=santa, receiver=receiver)
    
    # Создаем чаты для каждого пользователя
    for user in users:
        # Находим кто является Сантой для этого пользователя
        santa_pair = SantaPair.objects.get(room=room, receiver=user)
        my_santa = santa_pair.santa
        
        # Находим для кого этот пользователь является Сантой
        receiver_pair = SantaPair.objects.get(room=room, santa=user)
        my_receiver = receiver_pair.receiver
        
        # Создаем чат с моим Сантой
        Chat.objects.get_or_create(
            room=room,
            user=user,
            participant=my_santa,
            chat_type='my_santa'
        )
        
        # Создаем чат с моим получателем
        Chat.objects.get_or_create(
            room=room,
            user=user,
            participant=my_receiver,
            chat_type='my_receiver'
        )
    
    room.draw_completed = True
    room.save()
    
    return redirect('room_detail', room_id=room.id)

@login_required
def chat_detail(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    
    # Проверяем, что пользователь имеет доступ к чату
    if chat.user != request.user:
        return redirect('dashboard')
    
    messages = Message.objects.filter(chat=chat)
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.chat = chat
            message.sender = request.user
            message.save()
            
            # Создаем такое же сообщение в парном чате
            pair_chat = chat.get_pair_chat()
            if pair_chat:
                Message.objects.create(
                    chat=pair_chat,
                    sender=request.user,
                    content=message.content,
                    is_read=False
                )
            
            return redirect('chat_detail', chat_id=chat.id)
    else:
        form = MessageForm()
    
    # Помечаем сообщения как прочитанные
    messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    
    # Определяем название чата
    if chat.chat_type == 'my_santa':
        chat_title = f"🎅 Чат с моим Тайным Сантой"
    else:
        chat_title = f"🎁 Чат с моим получателем"
    
    now = datetime.now()
    yesterday = now - timedelta(days=1)

    context = {
        'chat': chat,
        'chat_title': chat_title,
        'messages': messages,
        'form': form,
        'other_user': chat.participant,
        'yesterday': yesterday, 
    }
    
    return render(request, 'chat_detail.html', context)

@login_required
def send_message(request, chat_id):
    """Отправка сообщения через AJAX"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        chat = get_object_or_404(Chat, id=chat_id)
        
        # Проверяем доступ
        if chat.user != request.user:
            return JsonResponse({'error': 'No access'}, status=403)
        
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        video = request.FILES.get('video')
        
        # Проверяем, что есть хотя бы текст или медиа
        if not content and not image and not video:
            return JsonResponse({'error': 'Empty message'}, status=400)
        
        # Проверяем размер файла
        if image and image.size > settings.MAX_UPLOAD_SIZE:
            return JsonResponse({'error': 'Image too large'}, status=400)
        
        if video and video.size > settings.MAX_UPLOAD_SIZE:
            return JsonResponse({'error': 'Video too large'}, status=400)
        
        # Создаем сообщение в основном чате
        message = Message.objects.create(
            chat=chat,
            sender=request.user,
            content=content if content else None,
            image=image,
            video=video
        )
        
        # Создаем такое же сообщение в парном чате
        pair_chat = chat.get_pair_chat()
        if pair_chat:
            pair_message = Message.objects.create(
                chat=pair_chat,
                sender=request.user,
                content=content if content else None,
                is_read=False
            )
            
            # Копируем файлы для парного сообщения
            if image:
                fs = FileSystemStorage()
                filename = fs.save(f'chat_images/{image.name}', image)
                pair_message.image = filename
                pair_message.save()
            
            if video:
                fs = FileSystemStorage()
                filename = fs.save(f'chat_videos/{video.name}', video)
                pair_message.video = filename
                pair_message.save()
        
        # Подготавливаем данные для ответа
        response_data = {
            'success': True,
            'id': message.id,
            'sender': request.user.get_full_name() or request.user.phone,
            'content': content,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'message_type': message.message_type
        }
        
        # Добавляем URL медиафайлов если они есть
        if message.image:
            response_data['image_url'] = message.image.url
        if message.video:
            response_data['video_url'] = message.video.url
        
        return JsonResponse(response_data)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def get_messages(request, chat_id):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        chat = get_object_or_404(Chat, id=chat_id)
        
        # Проверяем доступ
        if chat.user != request.user:
            return JsonResponse({'error': 'No access'}, status=403)
        
        # Получаем параметр last_id для фильтрации новых сообщений
        last_id = request.GET.get('last_id', 0)
        try:
            last_id = int(last_id)
        except (ValueError, TypeError):
            last_id = 0
        
        # Фильтруем сообщения, которые новее last_id
        messages = Message.objects.filter(chat=chat, id__gt=last_id).order_by('timestamp')

        # Помечаем непрочитанные сообщения как прочитанные
        unread_messages = messages.filter(is_read=False).exclude(sender=request.user)
        if unread_messages.exists():
            unread_messages.update(is_read=True)
        
        messages_data = []
        for message in messages:
            message_data = {
                'id': message.id,
                'sender': message.sender.get_full_name() or message.sender.phone,
                'content': message.content,
                'timestamp': message.timestamp.strftime('%H:%M'),
                'is_own': message.sender == request.user,
                'message_type': message.message_type
            }
            
            # Добавляем URL медиафайлов
            if message.image:
                message_data['image_url'] = message.image.url
            if message.video:
                message_data['video_url'] = message.video.url
                
            messages_data.append(message_data)
        
        return JsonResponse({'messages': messages_data})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def mark_messages_read(request, chat_id):
    """Помечает все сообщения в чате как прочитанные"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        chat = get_object_or_404(Chat, id=chat_id)
        
        # Проверяем доступ
        if chat.user != request.user:
            return JsonResponse({'error': 'No access'}, status=403)
        
        # Помечаем все непрочитанные сообщения (кроме своих) как прочитанные
        Message.objects.filter(
            chat=chat,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)



@login_required
def delete_room(request, room_id):
    """Удаление комнаты администратором"""
    room = get_object_or_404(Room, id=room_id)
    
    # Проверяем, что пользователь - администратор комнаты
    if room.admin != request.user:
        messages.error(request, 'Вы не можете удалить эту комнату')
        return redirect('dashboard')
    
    if request.method == 'POST':
        room_name = room.name
        room.delete_room()
        messages.success(request, f'Комната "{room_name}" успешно удалена')
        return redirect('dashboard')
    
    return redirect('room_detail', room_id=room.id)



@login_required
def join_room_with_name(request, room_id):
    """Присоединение к комнате с указанием имени"""
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        display_name = request.POST.get('display_name', '').strip()
        
        if not display_name:
            messages.error(request, 'Пожалуйста, укажите имя для этой комнаты')
            return redirect('room_detail', room_id=room.id)
        
        # Создаем участника с указанным именем
        participant, created = Participant.objects.get_or_create(
            user=request.user,
            room=room,
            defaults={'display_name': display_name}
        )
        
        if not created:
            participant.display_name = display_name
            participant.save()
        
        messages.success(request, f'Вы успешно присоединились к комнате как "{display_name}"')
        return redirect('room_detail', room_id=room.id)
    
    return redirect('dashboard')


def support_page(request):
    """Страница поддержки"""
    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        email = request.POST.get('email', '').strip()
        
        if message_text:
            # Сохраняем сообщение в базу данных
            SupportMessage.objects.create(
                user=request.user if request.user.is_authenticated else None,
                email=email,
                message=message_text
            )
            
            # # Можно добавить отправку email администратору
            # try:
            #     send_mail(
            #         'Новое сообщение поддержки - Тайный Санта',
            #         f'Сообщение: {message_text}\nEmail: {email}\nПользователь: {request.user if request.user.is_authenticated else "Аноним"}',
            #         'noreply@secretsanta.ru',
            #         ['admin@secretsanta.ru'],  # Ваш email
            #         fail_silently=True,
            #     )
            # except Exception as e:
            #     print(f"Ошибка отправки email: {e}")
            
            messages.success(request, '✅ Ваше сообщение отправлено! Спасибо за обратную связь.')
            return redirect('support')
        else:
            messages.error(request, '❌ Пожалуйста, напишите ваше сообщение')
    
    return render(request, 'support.html')


from django.http import JsonResponse

@login_required
def get_user_chats(request):
    """Получение списка чатов пользователя для мобильного приложения"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        user_chats = Chat.objects.filter(user=request.user).select_related('room', 'participant')
        
        chats_data = []
        for chat in user_chats:
            last_message = chat.message_set.last()
            unread_count = chat.message_set.filter(is_read=False).exclude(sender=request.user).count()
            
            chats_data.append({
                'id': chat.id,
                'chat_type': chat.chat_type,
                'room_name': chat.room.name,  # Убедитесь, что это поле есть
                'url': f'/chat/{chat.id}/',
                'last_message': {
                    'content': last_message.content if last_message else None,
                    'timestamp': last_message.timestamp.isoformat() if last_message else None
                } if last_message else None,
                'unread_count': unread_count
            })
        
        return JsonResponse({'chats': chats_data})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def toggle_participants_visibility(request, room_id):
    """Переключение видимости списка участников"""
    room = get_object_or_404(Room, id=room_id)
    
    # Проверяем, что пользователь - администратор комнаты
    if room.admin != request.user:
        return JsonResponse({'error': 'No permission'}, status=403)
    
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        room.show_participants = not room.show_participants
        room.save()
        
        return JsonResponse({
            'success': True,
            'show_participants': room.show_participants,
            'message': 'Настройки сохранены'
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)




# Добавьте функции для работы с секретными вопросами
@login_required
def security_question_setup(request):
    """
    Настройка секретного вопроса для восстановления пароля
    """
    if request.method == 'POST':
        form = SecurityQuestionSetupForm(request.POST, instance=request.user)
        if form.is_valid():
            # Получаем очищенные данные из формы
            security_question = form.cleaned_data['security_question']
            security_question_custom = form.cleaned_data.get('security_question_custom', '')
            security_answer = form.cleaned_data['security_answer']
            
            # Если выбран кастомный вопрос, используем его
            if security_question == 'custom' and security_question_custom:
                # Сохраняем кастомный вопрос как текст
                request.user.security_question = security_question_custom
            else:
                # Сохраняем текст стандартного вопроса
                question_dict = dict(SECURITY_QUESTIONS)
                request.user.security_question = question_dict.get(security_question)
            
            # Сохраняем ответ (в нижнем регистре)
            request.user.security_answer = security_answer.lower().strip()
            request.user.save()
            
            messages.success(request, 
                '✅ Секретный вопрос успешно установлен! '
                'Теперь вы можете использовать его для восстановления пароля.'
            )
            return redirect('dashboard')
    else:
        form = SecurityQuestionSetupForm(instance=request.user)
    
    # Убедитесь, что choices правильно устанавливаются
    form.fields['security_question'].choices = SECURITY_QUESTIONS
    
    return render(request, 'security_question_setup.html', {
        'form': form,
    })

def password_reset_request(request):
    """
    Первый шаг - запрос сброса пароля по номеру телефона
    """
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            try:
                user = User.objects.get(phone=phone)
                
                # Проверяем, установлен ли секретный вопрос
                if not user.security_question or not user.security_answer:
                    messages.error(request, 
                        '❌ Для вашего аккаунта не установлен секретный вопрос. '
                        'Обратитесь в поддержку для восстановления пароля.'
                    )
                    return redirect('support')
                
                # Сохраняем информацию в сессии
                request.session['password_reset_phone'] = phone
                request.session['password_reset_user_id'] = user.id
                
                messages.info(request, 
                    'Ответьте на ваш секретный вопрос для подтверждения личности.'
                )
                return redirect('security_question_verify')
                    
            except User.DoesNotExist:
                messages.error(request, 'Пользователь с таким номером телефона не найден.')
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'password_reset_request.html', {'form': form})

def security_question_verify(request):
    """
    Второй шаг - ответ на секретный вопрос
    """
    # Проверяем, что пользователь прошел первый шаг
    phone = request.session.get('password_reset_phone')
    user_id = request.session.get('password_reset_user_id')
    
    if not all([phone, user_id]):
        messages.error(request, 'Сессия истекла. Начните процесс восстановления заново.')
        return redirect('password_reset_request')
    
    try:
        user = User.objects.get(id=user_id, phone=phone)
        
        if request.method == 'POST':
            form = SecurityAnswerForm(request.POST, user=user)
            if form.is_valid():
                # Ответ верный, создаем токен для сброса пароля
                token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timedelta(hours=24)
                
                # Делаем недействительными предыдущие токены
                PasswordResetToken.objects.filter(user=user).update(is_used=True)
                
                # Создаем новый токен
                PasswordResetToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=expires_at
                )
                
                # Очищаем сессию
                del request.session['password_reset_phone']
                del request.session['password_reset_user_id']
                
                # Перенаправляем на страницу сброса пароля
                return redirect('password_reset_confirm', token=token)
        else:
            form = SecurityAnswerForm(user=user)
        
        # Маскируем вопрос для безопасности
        masked_question = user.security_question
        # if len(masked_question) > 3:
        #     masked_question = masked_question[:3] + '...' + masked_question[-3:] if len(masked_question) > 6 else masked_question
        
        return render(request, 'security_question_verify.html', {
            'form': form,
            'user': user,
            'masked_question': masked_question
        })
        
    except User.DoesNotExist:
        messages.error(request, 'Ошибка сессии. Начните процесс восстановления заново.')
        return redirect('password_reset_request')

def password_reset_confirm(request, token):
    """
    Третий шаг - установка нового пароля
    """
    try:
        reset_token = PasswordResetToken.objects.get(token=token, is_used=False)
        if not reset_token.is_valid():
            messages.error(request, 'Ссылка для сброса пароля недействительна или устарела.')
            return redirect('password_reset_request')
        
        if request.method == 'POST':
            form = PasswordResetForm(request.POST)
            if form.is_valid():
                # Устанавливаем новый пароль
                user = reset_token.user
                new_password = form.cleaned_data['new_password1']
                user.set_password(new_password)
                user.save()
                
                # Помечаем токен как использованный
                reset_token.is_used = True
                reset_token.save()
                
                messages.success(request, '✅ Пароль успешно изменен! Теперь вы можете войти с новым паролем.')
                return redirect('password_reset_complete')
        else:
            form = PasswordResetForm()
        
        return render(request, 'password_reset_confirm.html', {
            'form': form,
            'token': token,
            'user': reset_token.user
        })
        
    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Ссылка для сброса пароля недействительна.')
        return redirect('password_reset_request')

def password_reset_complete(request):
    """
    Завершение процесса сброса пароля
    """
    return render(request, 'password_reset_complete.html')