from django import forms
from .models import PaymentConfig, SupportTicket, SystemSettings

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = '__all__'
        widgets = {
            'maintenance_mode': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-purple-600'}),
            'registration_fee': forms.NumberInput(attrs={'class': 'form-input'}),
            'default_roi_percentage': forms.NumberInput(attrs={'class': 'form-input'}),
            'sponsor_bonus_level_1': forms.NumberInput(attrs={'class': 'form-input'}),
            'sponsor_bonus_level_2': forms.NumberInput(attrs={'class': 'form-input'}),
            'min_withdrawal': forms.NumberInput(attrs={'class': 'form-input'}),
        }

class PaymentConfigForm(forms.ModelForm):
    class Meta:
        model = PaymentConfig
        fields = '__all__'
        widgets = {
            'provider_name': forms.TextInput(attrs={'class': 'form-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-green-500'}),
            'api_key': forms.TextInput(attrs={'class': 'form-input'}),
            'secret_key': forms.PasswordInput(attrs={'class': 'form-input', 'render_value': True}),
            'environment': forms.Select(attrs={'class': 'form-input bg-gray-800 text-white'}),
            'webhook_url': forms.URLInput(attrs={'class': 'form-input'}),
        }


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ('subject', 'message', 'priority')
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'field-control',
                'placeholder': 'Objet de votre demande',
            }),
            'message': forms.Textarea(attrs={
                'class': 'field-control',
                'rows': 4,
                'placeholder': 'Expliquez votre besoin',
            }),
            'priority': forms.Select(attrs={'class': 'field-control'}),
        }


class AdminSupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ('status', 'priority', 'admin_response')
        widgets = {
            'status': forms.Select(attrs={'class': 'form-input'}),
            'priority': forms.Select(attrs={'class': 'form-input'}),
            'admin_response': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
        }
