from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Room, Message

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
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Название комнаты'
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
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Введите сообщение...'
            }),
        }


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