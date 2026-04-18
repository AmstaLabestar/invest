from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(label="Prénom", max_length=150, required=True)
    last_name = forms.CharField(label="Nom", max_length=150, required=True)
    phone_number = forms.CharField(label="Numéro de téléphone", max_length=15, required=True)
    sponsor_code = forms.CharField(label="Code parrain (Optionnel)", max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'phone_number')

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '')
        phone = phone.replace(' ', '')
        
        # Automatisation de l'indicatif +226 si manquant
        if not phone.startswith('+'):
            if phone.startswith('226'):
                phone = '+' + phone
            else:
                # Ajout automatique du préfixe
                phone = '+226' + phone
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.phone_number = self.cleaned_data.get('phone_number')
        
        # Logique de parrainage
        sponsor_code = self.cleaned_data.get('sponsor_code')
        if sponsor_code:
            try:
                sponsor = User.objects.get(username=sponsor_code)
                user.sponsor = sponsor
            except User.DoesNotExist:
                pass # Si le parrain n'existe pas, on ignore silencieusement pour ne pas bloquer l'inscription
                
        if commit:
            user.save()
        return user

class CustomUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'balance', 'points', 'is_active', 'is_platform_admin')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'balance': forms.NumberInput(attrs={'class': 'form-input'}),
            'points': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-green-500'}),
            'is_platform_admin': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-purple-600'}),
        }
