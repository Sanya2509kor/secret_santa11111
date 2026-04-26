from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Participant, User, Room, Message

class PhoneUserCreationForm(UserCreationForm):
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Номер телефона',
            'pattern': r'[+]?[7-8]?[0-9\s\-\(\)]{10,15}',
            'title': 'Введите номер телефона'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Никнейм'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Пароль'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Подтверждение пароля'
        })
    )
    
    class Meta:
        model = User
        fields = ['phone', 'first_name', 'password1', 'password2']
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        # Базовая очистка номера телефона
        phone = ''.join(filter(str.isdigit, phone))
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('Пользователь с таким номером телефона уже существует.')
        return phone

class PhoneAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Номер телефона'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Пароль'
        })
    )

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Название комнаты'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Описание'
            }), 
        }

class JoinRoomForm(forms.Form):
    code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Код комнаты'
        })
    )

class MessageForm(forms.ModelForm):
    content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Введите сообщение...',
            'id': 'message-content'
        }),
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'd-none',
            'id': 'image-input',
            'accept': 'image/*'
        })
    )
    video = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'd-none',
            'id': 'video-input',
            'accept': 'video/*'
        })
    )
    
    class Meta:
        model = Message
        fields = ['content', 'image', 'video']


class WishlistForm(forms.ModelForm):
    class Meta:
        model = User  # или создайте отдельную модель для вишлиста
        fields = ['wishlist']  # нужно добавить поле wishlist в модель User
        
    wishlist = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 5, 
            'placeholder': 'Что бы вы хотели получить в подарок?'
        }),
        required=False
    )


class ParticipantNameForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['display_name']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваше имя в этой комнате',
                'maxlength': '30'
            })
        }
    
    def clean_display_name(self):
        display_name = self.cleaned_data.get('display_name')
        if display_name:
            display_name = display_name.strip()
            if len(display_name) < 2:
                raise forms.ValidationError('Имя должно содержать минимум 2 символа')
            if len(display_name) > 30:
                raise forms.ValidationError('Имя не должно превышать 30 символов')
        return display_name
    


# Добавьте в forms.py

SECURITY_QUESTIONS = [
    ('', '--- Выберите вопрос ---'),
    ('childhood_nickname', 'Какое было ваше детское прозвище?'),
    ('first_pet', 'Как звали вашего первого питомца?'),
    ('birth_city', 'В каком городе вы родились?'),
    ('mother_maiden_name', 'Девичья фамилия вашей матери?'),
    ('favorite_teacher', 'Фамилия вашего любимого учителя в школе?'),
    ('first_car', 'Марка и модель вашей первой машины?'),
    ('childhood_friend', 'Имя вашего лучшего друга в детстве?'),
    ('favorite_book', 'Ваша любимая книга в детстве?'),
    ('first_concert', 'На какой первый концерт вы ходили?'),
    ('custom', 'Свой вопрос...'),
]

class SecurityQuestionSetupForm(forms.ModelForm):
    security_question = forms.ChoiceField(
        choices=SECURITY_QUESTIONS,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_security_question'
        }),
        label='Секретный вопрос *',
        required=True
    )
    
    security_question_custom = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Введите ваш вопрос...',
            'maxlength': '200',
            'id': 'id_security_question_custom'
        }),
        label='Ваш вопрос'
    )
    
    security_answer = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ваш ответ...',
            'maxlength': '100',
            'id': 'id_security_answer'
        }),
        label='Ответ на вопрос *',
        required=True
    )
    
    class Meta:
        model = User
        fields = ['security_question', 'security_answer']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убедимся, что choices установлены
        self.fields['security_question'].choices = SECURITY_QUESTIONS

class PasswordResetRequestForm(forms.Form):
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Номер телефона',
            'pattern': '[\+]?[7-8]?[0-9\s\-\(\)]{10,15}'
        })
    )
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        # Очистка номера телефона
        phone = ''.join(filter(str.isdigit, phone))
        if not User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('Пользователь с таким номером телефона не найден.')
        return phone

class SecurityAnswerForm(forms.Form):
    security_answer = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Введите ваш ответ...',
            'autocomplete': 'off'
        }),
        label=''
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_security_answer(self):
        answer = self.cleaned_data.get('security_answer')
        if not answer:
            raise forms.ValidationError('Введите ответ на секретный вопрос')
        
        if self.user and not self.user.verify_security_answer(answer):
            raise forms.ValidationError('Неверный ответ на секретный вопрос')
        
        return answer

class PasswordResetForm(forms.Form):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Новый пароль'
        }),
        min_length=8,
        label='Новый пароль'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Подтвердите новый пароль'
        }),
        label='Подтверждение пароля'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают.')
        
        return cleaned_data