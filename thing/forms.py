from django import forms

class UploadSkillPlanForm(forms.Form):
    name = forms.CharField(max_length=64)
    sptype = forms.CharField(max_length=10)
    file = forms.FileField(required=False)
    visibility = forms.IntegerField()
