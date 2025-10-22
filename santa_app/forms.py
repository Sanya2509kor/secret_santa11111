from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Participant, User, Room, Message

class PhoneUserCreationForm(UserCreationForm):
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Номер телефона',
            'pattern': '[\+]?[7-8]?[0-9\s\-\(\)]{10,15}',
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