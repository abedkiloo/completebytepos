from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.db.models import Q
from products.models import Product
import barcode
from barcode.writer import ImageWriter
from barcode import Code128, EAN13, EAN8
import qrcode
from io import BytesIO
import base64
from PIL import Image
import logging

# Get logger for this module
logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_barcode(request):
    """Generate barcode image for a product"""
    product_id = request.query_params.get('product_id', None)
    barcode_value = request.query_params.get('barcode', None)
    # Use 'barcode_format' instead of 'format' to avoid conflict with DRF's format suffix handling
    format_type = request.query_params.get('barcode_format') or request.query_params.get('format', 'code128')
    width = int(request.query_params.get('width', 2))
    height = int(request.query_params.get('height', 100))
    include_text = request.query_params.get('include_text', 'true').lower() == 'true'
    
    if not product_id and not barcode_value:
        return Response(
            {'error': 'product_id or barcode parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get barcode value
    if product_id:
        try:
            product = Product.objects.get(id=product_id)
            barcode_value = product.barcode or product.sku
        except Product.DoesNotExist:
            logger.error(f"Product not found with ID: {product_id}")
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    if not barcode_value:
        return Response(
            {'error': 'Product has no barcode or SKU'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Generate barcode image
        if format_type == 'qrcode':
            img = _generate_qrcode(barcode_value, width, height)
        else:
            img = _generate_barcode(barcode_value, format_type, width, height, include_text)
        
        # Convert to base64 for JSON response
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return Response({
            'barcode': barcode_value,
            'format': format_type,
            'image': f'data:image/png;base64,{img_str}',
            'product_id': product_id,
        })
    except ValueError as e:
        logger.error(f"ValueError generating barcode: {str(e)}")
        return Response(
            {'error': f'Invalid barcode format or value: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Exception generating barcode: {str(e)}", exc_info=True)
        return Response(
            {'error': f'Failed to generate barcode: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_barcode_image(request):
    """Get barcode as image file (for direct printing)"""
    product_id = request.query_params.get('product_id', None)
    barcode_value = request.query_params.get('barcode', None)
    # Use 'barcode_format' instead of 'format' to avoid conflict with DRF's format suffix handling
    format_type = request.query_params.get('barcode_format') or request.query_params.get('format', 'code128')
    width = int(request.query_params.get('width', 2))
    height = int(request.query_params.get('height', 100))
    include_text = request.query_params.get('include_text', 'true').lower() == 'true'
    
    if not product_id and not barcode_value:
        return Response(
            {'error': 'product_id or barcode parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if product_id:
        try:
            product = Product.objects.get(id=product_id)
            barcode_value = product.barcode or product.sku
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    try:
        if format_type == 'qrcode':
            img = _generate_qrcode(barcode_value, width, height)
        else:
            img = _generate_barcode(barcode_value, format_type, width, height, include_text)
        
        response = HttpResponse(content_type='image/png')
        img.save(response, format='PNG')
        return response
    except ValueError as e:
        return Response(
            {'error': f'Invalid barcode format or value: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return Response(
            {'error': f'Failed to generate barcode image: {str(e)}', 'detail': error_trace},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_missing_barcodes(request):
    """Auto-generate barcodes for products that don't have them"""
    product_ids = request.data.get('product_ids', [])
    # Use 'barcode_format' instead of 'format' to avoid conflict with DRF's format suffix handling
    format_type = request.data.get('barcode_format') or request.data.get('format', 'code128')
    prefix = request.data.get('prefix', 'BC')
    
    if not product_ids:
        # Get all products without barcodes
        products = Product.objects.filter(Q(barcode__isnull=True) | Q(barcode=''))
    else:
        products = Product.objects.filter(id__in=product_ids)
    
    generated = []
    errors = []
    
    for product in products:
        try:
            # Generate barcode from SKU or create new one
            if product.sku:
                barcode_value = f"{prefix}{product.sku}"
            else:
                import uuid
                barcode_value = f"{prefix}{uuid.uuid4().hex[:10].upper()}"
            
            # Ensure uniqueness
            counter = 1
            original_value = barcode_value
            while Product.objects.filter(barcode=barcode_value).exclude(id=product.id).exists():
                barcode_value = f"{original_value}{counter:03d}"
                counter += 1
            
            product.barcode = barcode_value
            product.save()
            
            generated.append({
                'product_id': product.id,
                'product_name': product.name,
                'barcode': barcode_value,
            })
        except Exception as e:
            errors.append({
                'product_id': product.id,
                'product_name': product.name,
                'error': str(e),
            })
    
    return Response({
        'generated': len(generated),
        'errors': len(errors),
        'products': generated,
        'error_list': errors,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def print_barcode_labels(request):
    """Generate printable barcode labels for multiple products"""
    product_ids = request.data.get('product_ids', [])
    # Use 'barcode_format' instead of 'format' to avoid conflict with DRF's format suffix handling
    format_type = request.data.get('barcode_format') or request.data.get('format', 'code128')
    label_width = float(request.data.get('label_width', 4))
    label_height = float(request.data.get('label_height', 2))
    include_price = request.data.get('include_price', False)
    include_name = request.data.get('include_name', True)
    quantity = int(request.data.get('quantity', 1))
    
    if not product_ids:
        return Response(
            {'error': 'product_ids is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        products = Product.objects.filter(id__in=product_ids)
        
        # Generate PDF with labels using reportlab
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        page_width, page_height = letter
        
        x = 0.5 * inch
        y = page_height - 0.5 * inch
        labels_per_row = int(page_width / (label_width * inch))
        row = 0
        col = 0
        
        for product in products:
            for qty in range(quantity):
                if col >= labels_per_row:
                    col = 0
                    row += 1
                    y -= label_height * inch
                    
                    if y < 1 * inch:
                        c.showPage()
                        y = page_height - 0.5 * inch
                        row = 0
                
                # Generate barcode image
                barcode_value = product.barcode or product.sku
                if format_type == 'qrcode':
                    barcode_img = _generate_qrcode(barcode_value, 1, 50)
                else:
                    barcode_img = _generate_barcode(barcode_value, format_type, 1, 50, True)
                
                # Position
                label_x = x + (col * label_width * inch)
                label_y = y
                
                # Draw barcode
                img_buffer = BytesIO()
                barcode_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                c.drawImage(ImageReader(img_buffer), label_x, label_y - 0.5 * inch, 
                          width=label_width * inch - 0.2 * inch, 
                          height=0.8 * inch, preserveAspectRatio=True)
                
                # Draw product name
                if include_name:
                    c.setFont("Helvetica", 8)
                    name = product.name[:30]
                    c.drawString(label_x + 0.1 * inch, label_y - 0.6 * inch, name)
                
                # Draw barcode value
                c.setFont("Helvetica", 7)
                c.drawString(label_x + 0.1 * inch, label_y - 0.7 * inch, barcode_value)
                
                # Draw price
                if include_price:
                    c.setFont("Helvetica", 9)
                    price_text = f"KES {product.price:.2f}"
                    c.drawString(label_x + 0.1 * inch, label_y - 0.85 * inch, price_text)
                
                col += 1
        
        c.save()
        buffer.seek(0)
        
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="barcode_labels.pdf"'
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Failed to generate labels: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _generate_barcode(value, format_type, width, height, include_text):
    """Generate barcode image"""
    try:
        # Convert value to string and clean it
        value = str(value).strip()
        
        if format_type == 'code128':
            code = Code128(value, writer=ImageWriter())
        elif format_type == 'ean13':
            if not value.isdigit():
                raise ValueError('EAN13 requires numeric digits only')
            if len(value) not in [12, 13]:
                raise ValueError('EAN13 requires 12 or 13 digits')
            code = EAN13(value, writer=ImageWriter())
        elif format_type == 'ean8':
            if not value.isdigit():
                raise ValueError('EAN8 requires numeric digits only')
            if len(value) not in [7, 8]:
                raise ValueError('EAN8 requires 7 or 8 digits')
            code = EAN8(value, writer=ImageWriter())
        else:
            code = Code128(value, writer=ImageWriter())
        
        options = {
            'module_width': width,
            'module_height': height,
            'quiet_zone': 2,
            'font_size': 10,
            'text_distance': 5,
            'write_text': include_text,
        }
        
        buffer = BytesIO()
        code.write(buffer, options=options)
        buffer.seek(0)
        img = Image.open(buffer)
        return img
    except Exception as e:
        raise ValueError(f'Invalid barcode format or value: {str(e)}')


def _generate_qrcode(value, width, height):
    """Generate QR code image"""
    try:
        # Convert value to string and clean it
        value = str(value).strip()
        if not value:
            raise ValueError('QR code value cannot be empty')
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=max(width, 10),  # Ensure minimum box size
            border=2,
        )
        qr.add_data(value)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        # Resize if needed (height is used as target size for square QR code)
        if height and height > 0:
            target_size = max(height, 100)  # Minimum 100px
            img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        raise ValueError(f'Failed to generate QR code: {str(e)}')
