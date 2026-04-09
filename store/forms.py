from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'original_price', 'discount_price', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter product name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter product description', 'rows': 4}),
            'original_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter original price'}),
            'discount_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter discount price'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        original = cleaned_data.get('original_price')
        discount = cleaned_data.get('discount_price')

        if original is not None and discount is not None:
            if discount > original:
                raise forms.ValidationError("Discount price cannot be greater than original price.")
            if discount <= 0 or original <= 0:
                raise forms.ValidationError("Prices must be greater than zero.")