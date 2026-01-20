from django.db import models
from django.conf import settings
from django.core.validators import EmailValidator, MinValueValidator
from decimal import Decimal


class Employee(models.Model):
    """Employee Management Model"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]
    
    DEPARTMENT_CHOICES = [
        ('production', 'Production'),
        ('sales', 'Sales'),
        ('admin', 'Administration'),
        ('finance', 'Finance'),
        ('management', 'Management'),
        ('other', 'Other'),
    ]
    
    # Basic Information
    employee_id = models.CharField(max_length=50, unique=True, help_text='Unique employee ID')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()], blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Employment Details
    position = models.CharField(max_length=100, help_text='Job title/position')
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, default='other')
    hire_date = models.DateField(help_text='Date of hire')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Compensation
    salary = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        null=True,
        blank=True,
        help_text='Monthly salary'
    )
    
    # Additional Information
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text='Additional notes about the employee')
    
    # Audit Fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['status']),
            models.Index(fields=['department']),
        ]
    
    def __str__(self):
        return f"{self.employee_id} - {self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_active(self):
        return self.status == 'active'
