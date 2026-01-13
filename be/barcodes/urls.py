from django.urls import path
from .views import (
    generate_barcode,
    get_barcode_image,
    generate_missing_barcodes,
    print_barcode_labels,
)

urlpatterns = [
    path('generate/', generate_barcode, name='barcode-generate'),
    path('generate', generate_barcode, name='barcode-generate-no-slash'),
    path('image/', get_barcode_image, name='barcode-image'),
    path('image', get_barcode_image, name='barcode-image-no-slash'),
    path('generate_missing/', generate_missing_barcodes, name='barcode-generate-missing'),
    path('print_labels/', print_barcode_labels, name='barcode-print-labels'),
]
