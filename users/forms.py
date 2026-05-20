from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(label="Prenom", max_length=150, required=True)
    last_name = forms.CharField(label="Nom", max_length=150, required=True)
    email = forms.EmailField(label="Email", required=True)
    phone_number = forms.CharField(label="Numero de telephone", max_length=15, required=True)
    sponsor_code = forms.CharField(label="Code parrain", max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'phone_number')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Cette adresse email est deja utilisee.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').replace(' ', '')
        if not phone.startswith('+'):
            phone = f"+{phone}" if phone.startswith('226') else f"+226{phone}"
        return phone

    def clean_sponsor_code(self):
        sponsor_code = self.cleaned_data.get('sponsor_code', '').strip()
        if not sponsor_code:
            return ''

        normalized_code = sponsor_code
        if sponsor_code.upper().startswith('INV-'):
            normalized_code = sponsor_code.split('-')[-1]

        sponsor_exists = User.objects.filter(username__iexact=normalized_code).exists()
        if not sponsor_exists and normalized_code.isdigit():
            sponsor_exists = User.objects.filter(id=normalized_code).exists()

        if not sponsor_exists:
            raise forms.ValidationError("Code parrain invalide.")
        return sponsor_code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.email = self.cleaned_data.get('email')
        user.phone_number = self.cleaned_data.get('phone_number')

        sponsor_code = self.cleaned_data.get('sponsor_code')
        if sponsor_code:
            normalized_code = sponsor_code
            if sponsor_code.upper().startswith('INV-'):
                normalized_code = sponsor_code.split('-')[-1]

            sponsor = None
            if normalized_code.isdigit():
                sponsor = User.objects.filter(id=normalized_code).first()
            if sponsor is None:
                sponsor = User.objects.filter(username__iexact=normalized_code).first()
            user.sponsor = sponsor

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
