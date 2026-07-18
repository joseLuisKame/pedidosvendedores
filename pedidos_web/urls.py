"""
URL configuration for pedidos_web project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.static import serve
from django.conf import settings
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('sw.js', lambda r: serve(r, 'sw.js', document_root=str(settings.BASE_DIR / 'pedidos_web' / 'static'))),
    path('importar/', views.import_master_files, name='import_csv'),
    path('buscar-articulos/', views.buscar_articulos, name='buscar_articulos'),
    path('crear-pedido/', views.crear_pedido, name='crear_pedido'),
    path('pedido-offline/', views.pedido_offline, name='pedido_offline'),
    path('pedidos/', views.pedidos, name='pedidos'),
    path('pedidos/<str:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
    path('clientes/', views.clientes, name='clientes'),
    path('articulos/', views.articulos, name='articulos'),
    path('exportar-pedidos/', views.exportar_pedidos, name='exportar_pedidos'),
    path('importar-maestros/', views.import_master_files, name='import_master_files'),
    path('api/data/', views.api_data, name='api_data'),
    path('api/sync/', views.api_sync, name='api_sync'),
]
