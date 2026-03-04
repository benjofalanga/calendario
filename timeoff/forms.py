from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Country, EmployeeProfile, PublicHoliday


class DaySelectionForm(forms.Form):
    selected_dates = forms.CharField(widget=forms.HiddenInput(), required=True)


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ["name", "code"]

    def clean_code(self):
        return self.cleaned_data["code"].upper().strip()


class PublicHolidayForm(forms.ModelForm):
    class Meta:
        model = PublicHoliday
        fields = ["country", "name", "date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class EmployeeProfileUpdateForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none())
    country = forms.ModelChoiceField(queryset=Country.objects.all(), required=False)
    role = forms.ChoiceField(choices=EmployeeProfile.ROLE_CHOICES)
    annual_day_off_allowance = forms.IntegerField(
        min_value=0,
        max_value=365,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "placeholder": "Leave blank to keep current (default 30)",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("carryover_year", None)
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(profile__isnull=False).order_by("username")


class ManagerUserCreateForm(UserCreationForm):
    email = forms.EmailField(required=False)
    country = forms.ModelChoiceField(queryset=Country.objects.all(), required=False)
    role = forms.ChoiceField(choices=EmployeeProfile.ROLE_CHOICES, initial=EmployeeProfile.ROLE_EMPLOYEE)
    annual_day_off_allowance = forms.IntegerField(min_value=0, max_value=365, initial=30)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
            profile, _ = EmployeeProfile.objects.get_or_create(user=user)
            profile.country = self.cleaned_data["country"]
            profile.role = self.cleaned_data["role"]
            profile.annual_day_off_allowance = self.cleaned_data["annual_day_off_allowance"]
            profile.save()
        return user


class EmployeeDirectUpdateForm(forms.Form):
    email = forms.EmailField(required=False)
    country = forms.ModelChoiceField(queryset=Country.objects.all(), required=False)
    role = forms.ChoiceField(choices=EmployeeProfile.ROLE_CHOICES)
    annual_day_off_allowance = forms.IntegerField(
        min_value=0,
        max_value=365,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "placeholder": "Leave blank to keep current (default 30)",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("carryover_year", None)
        super().__init__(*args, **kwargs)
