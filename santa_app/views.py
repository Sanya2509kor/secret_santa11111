from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
import random
from .models import Room, Participant, SantaPair, Chat, Message, User
from .forms import PhoneUserCreationForm, PhoneAuthenticationForm, RoomForm, JoinRoomForm, MessageForm, WishlistForm

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
            return redirect('dashboard')
    else:
        form = PhoneAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
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
                Participant.objects.create(user=request.user, room=room)
                return redirect('room_detail', room_id=room.id)
                
        elif form_type == 'join_room':
            join_form = JoinRoomForm(request.POST)
            
            if join_form.is_valid():
                code = join_form.cleaned_data['code'].upper()
                try:
                    room = Room.objects.get(code=code, is_active=True)
                    if not Participant.objects.filter(user=request.user, room=room).exists():
                        Participant.objects.create(user=request.user, room=room)
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
    chats_with_unread = []
    
    for chat in user_chats:
        unread_count = chat.get_unread_count()
        chats_with_unread.append({
            'chat': chat,
            'unread_count': unread_count
        })
    
    context = {
        'room': room,
        'participant': participant,
        'participants': participants,
        'my_santa': my_santa,
        'my_receiver': my_receiver,
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
    
    # Перемешиваем пользователей
    random.shuffle(users)
    
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
        chat_title = f"🎁 Чат с моим получателем ({chat.participant.get_full_name() or chat.participant.phone})"
    
    context = {
        'chat': chat,
        'chat_title': chat_title,
        'messages': messages,
        'form': form,
        'other_user': chat.participant,
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
        if content:
            # Создаем сообщение в основном чате
            message = Message.objects.create(
                chat=chat,
                sender=request.user,
                content=content
            )
            
            # Создаем такое же сообщение в парном чате
            pair_chat = chat.get_pair_chat()
            if pair_chat:
                Message.objects.create(
                    chat=pair_chat,
                    sender=request.user,
                    content=content,
                    is_read=False
                )
            
            return JsonResponse({
                'success': True,
                'id': message.id,  # Добавляем ID сообщения
                'sender': request.user.get_full_name() or request.user.phone,
                'content': content,
                'timestamp': message.timestamp.strftime('%H:%M')
            })
        
        return JsonResponse({'error': 'Empty message'}, status=400)
    
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
            messages_data.append({
                'id': message.id,
                'sender': message.sender.get_full_name() or message.sender.phone,
                'content': message.content,
                'timestamp': message.timestamp.strftime('%H:%M'),
                'is_own': message.sender == request.user,
            })
        
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