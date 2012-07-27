from django import forms

class UploadSkillPlanForm(forms.Form):
    name = forms.CharField(max_length=64)
    file = forms.FileField()
