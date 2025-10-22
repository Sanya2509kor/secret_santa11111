from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import uuid

class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('The Phone field must be set')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)

class User(AbstractUser):
    phone = models.CharField(max_length=20, unique=True)
    username = models.CharField(max_length=150, unique=False, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)  # Сделать необязательным
    wishlist = models.TextField(blank=True, null=True, verbose_name='Список желаний')
    last_name = models.CharField(max_length=30, blank=True, null=True)  # Сделать необязательным
    display_name = models.CharField(max_length=30, blank=True, null=True, verbose_name='Отображаемое имя')
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []  # Убрать email из обязательных
    
    objects = UserManager()
    
    def __str__(self):
        return f"{self.phone} ({self.first_name or 'No name'})"
    
    def get_display_name(self):
        """Возвращает отображаемое имя или телефон"""
        return self.display_name or self.first_name or self.phone
    
    def get_full_name(self):
        return self.display_name or self.first_name or self.phone
    
    def get_short_name(self):
        return self.first_name or self.phone

class Room(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=1000, verbose_name='Описание', blank=True, null=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    draw_completed = models.BooleanField(default=False)
    show_participants = models.BooleanField(default=False, verbose_name='Показывать участников?', blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = uuid.uuid4().hex[:6].upper()
        super().save(*args, **kwargs)

    def delete_room(self):
        """Метод для безопасного удаления комнаты"""
        # Удаляем все связанные объекты
        SantaPair.objects.filter(room=self).delete()
        Chat.objects.filter(room=self).delete()
        Message.objects.filter(chat__room=self).delete()
        Participant.objects.filter(room=self).delete()
        # Удаляем саму комнату
        self.delete()
    

    class Meta:
        verbose_name = 'Комнату'
        verbose_name_plural = 'Комнаты'
    
    def __str__(self):
        return self.name

class Participant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=30, verbose_name="Имя в комнате", blank=True)
    wishlist = models.TextField(blank=True, null=True, verbose_name="Пожелания к подарку")
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'room']
        verbose_name = 'Участника'
        verbose_name_plural = 'Участники'
    
    def __str__(self):
        return f"{self.get_display_name()} в {self.room.name}"
    
    def get_display_name(self):
        """Возвращает имя участника в комнате или основное имя пользователя"""
        return self.display_name or self.user.get_display_name()
    
    def save(self, *args, **kwargs):
        # Запрещаем изменение имени после создания
        if self.pk:
            original = Participant.objects.get(pk=self.pk)
            if original.display_name != self.display_name:
                raise ValueError("Имя в комнате нельзя изменить после присоединения")
        super().save(*args, **kwargs)


class SantaPair(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    santa = models.ForeignKey(User, on_delete=models.CASCADE, related_name='santa_for')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receiver_for')
    
    class Meta:
        unique_together = ['room', 'santa']
        verbose_name = 'Пару Санта-Получатель'
        verbose_name_plural = 'Пары Санта-Получатель'
    
    def __str__(self):
        return f"{self.santa.phone} -> {self.receiver.phone}"

class Chat(models.Model):
    CHAT_TYPES = [
        ('my_santa', 'Чат с моим Тайным Сантой'),
        ('my_receiver', 'Чат с моим получателем'),
    ]
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats')
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='participant_chats')
    chat_type = models.CharField(max_length=15, choices=CHAT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['room', 'user', 'chat_type']
        verbose_name = 'Чат'
        verbose_name_plural = 'Чаты'
    
    def __str__(self):
        return f"{self.user.phone} - {self.chat_type} - {self.participant.phone}"
    
    def get_pair_chat(self):
        """Находит парный чат для другого пользователя"""
        if self.chat_type == 'my_santa':
            # Если это чат "с моим Сантой", то парный чат - это чат "с моим получателем" у Санты
            pair_chat_type = 'my_receiver'
            pair_user = self.participant
            pair_participant = self.user
        else:  # my_receiver
            # Если это чат "с моим получателем", то парный чат - это чат "с моим Сантой" у получателя
            pair_chat_type = 'my_santa'
            pair_user = self.participant
            pair_participant = self.user
        
        try:
            return Chat.objects.get(
                room=self.room,
                user=pair_user,
                participant=pair_participant,
                chat_type=pair_chat_type
            )
        except Chat.DoesNotExist:
            return None
        
    def get_unread_count(self):
        """Возвращает количество непрочитанных сообщений в чате"""
        return Message.objects.filter(
            chat=self,
            is_read=False
        ).exclude(sender=self.user).count()

class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)  # Сделать необязательным
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    video = models.FileField(upload_to='chat_videos/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
    
    def __str__(self):
        return f"{self.sender.phone}: {self.content[:20] if self.content else 'Медиа'}"
    
    @property
    def message_type(self):
        if self.image:
            return 'image'
        elif self.video:
            return 'video'
        else:
            return 'text'
        

class SupportMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Сообщение поддержки'
        verbose_name_plural = 'Сообщения поддержки'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Сообщение от {self.email or 'анонима'} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"