from django.urls import path
from api.views.auth_views import LoginView, MeView, UserFirmaView
from api.views.user_views import UserListCreateView, UserDetailView
from api.views.planta_views import PlantaListCreateView, PlantaDetailView
from api.views.material_views import MaterialListCreateView, MaterialDetailView, MaterialPrecioView
from api.views.cliente_views import ClienteListCreateView, ClienteDetailView, ClientePdfView
from api.views.cliente_token_views import (
    ClienteTokenListCreateView, ClienteTokenRevocarView, VinculacionPublicaView,
)
from api.views.solicitud_views import SolicitudCotizacionListCreateView, SolicitudCotizacionDetailView
from api.views.cotizacion_views import (
    CotizacionListCreateView, CotizacionDetailView, CotizacionAprobarView, CotizacionPdfView,
)
from api.views.pago_views import PagoListCreateView, PagoComprobanteUploadView, PagoAprobarView
from api.views.orden_suministro_views import (
    OrdenSuministroListView, OrdenSuministroDetailView, OrdenSuministroNotificarView, OrdenSuministroPdfView,
)
from api.views.despacho_views import DespachoListCreateView, DespachoDetailView, DespachoPdfView
from api.views.tablero_views import TableroView, SeguimientoListCreateView
from api.views.control_despachos_views import ControlDespachosPdfView
from api.views.solicitud_token_views import (
    SolicitudTokenListCreateView, SolicitudTokenRevocarView, SolicitudPublicaView,
)


def p(route, view):
    """Registra la ruta con y sin slash final."""
    return [
        path(route, view),
        path(route.rstrip("/") + "/", view) if not route.endswith("/") else path(route.rstrip("/"), view),
    ]


urlpatterns = []

# Auth
urlpatterns += p("auth/login", LoginView.as_view())
urlpatterns += p("auth/me", MeView.as_view())
urlpatterns += p("auth/firma", UserFirmaView.as_view())

# Usuarios (admin)
urlpatterns += p("users/", UserListCreateView.as_view())
urlpatterns += p("users/<int:user_id>/", UserDetailView.as_view())

# Plantas
urlpatterns += p("plantas/", PlantaListCreateView.as_view())
urlpatterns += p("plantas/<int:planta_id>/", PlantaDetailView.as_view())

# Materiales
urlpatterns += p("materiales/<int:material_id>/precios/", MaterialPrecioView.as_view())
urlpatterns += p("materiales/<int:material_id>/", MaterialDetailView.as_view())
urlpatterns += p("materiales/", MaterialListCreateView.as_view())

# Links de vinculación (el comercial los genera, el cliente los usa)
urlpatterns += p("cliente-tokens/<int:token_id>/", ClienteTokenRevocarView.as_view())
urlpatterns += p("cliente-tokens/", ClienteTokenListCreateView.as_view())

# Links de pedidos (el cliente arma sus propias solicitudes de cotización)
urlpatterns += p("solicitud-tokens/<int:token_id>/", SolicitudTokenRevocarView.as_view())
urlpatterns += p("solicitud-tokens/", SolicitudTokenListCreateView.as_view())

# Formularios públicos — sin auth, el token es la credencial
urlpatterns += p("publico/vinculacion/<str:token>/", VinculacionPublicaView.as_view())
urlpatterns += p("publico/solicitud/<str:token>/", SolicitudPublicaView.as_view())

# Clientes
urlpatterns += p("clientes/<int:cliente_id>/pdf/", ClientePdfView.as_view())
urlpatterns += p("clientes/<int:cliente_id>/", ClienteDetailView.as_view())
urlpatterns += p("clientes/", ClienteListCreateView.as_view())

# Tablero de seguimiento del flujo
urlpatterns += p("tablero/", TableroView.as_view())

# Solicitudes de cotización
urlpatterns += p("solicitudes-cotizacion/<int:solicitud_id>/seguimientos/", SeguimientoListCreateView.as_view())
urlpatterns += p("solicitudes-cotizacion/<int:solicitud_id>/", SolicitudCotizacionDetailView.as_view())
urlpatterns += p("solicitudes-cotizacion/", SolicitudCotizacionListCreateView.as_view())

# Cotizaciones
urlpatterns += p("cotizaciones/<int:cotizacion_id>/aprobar/", CotizacionAprobarView.as_view())
urlpatterns += p("cotizaciones/<int:cotizacion_id>/pdf/", CotizacionPdfView.as_view())
urlpatterns += p("cotizaciones/<int:cotizacion_id>/", CotizacionDetailView.as_view())
urlpatterns += p("cotizaciones/", CotizacionListCreateView.as_view())

# Pagos
urlpatterns += p("pagos/<int:pago_id>/comprobante/", PagoComprobanteUploadView.as_view())
urlpatterns += p("pagos/<int:pago_id>/aprobar/", PagoAprobarView.as_view())
urlpatterns += p("pagos/", PagoListCreateView.as_view())

# Órdenes de suministro
urlpatterns += p("ordenes-suministro/<int:orden_id>/notificar/", OrdenSuministroNotificarView.as_view())
urlpatterns += p("ordenes-suministro/<int:orden_id>/pdf/", OrdenSuministroPdfView.as_view())
urlpatterns += p("ordenes-suministro/<int:orden_id>/", OrdenSuministroDetailView.as_view())
urlpatterns += p("ordenes-suministro/", OrdenSuministroListView.as_view())

# Control de despacho de materiales (consolidado por cliente, al vuelo)
urlpatterns += p("control-despachos/pdf/", ControlDespachosPdfView.as_view())

# Despachos (Control de Despacho y Recibo de Material)
urlpatterns += p("despachos/<int:despacho_id>/pdf/", DespachoPdfView.as_view())
urlpatterns += p("despachos/<int:despacho_id>/", DespachoDetailView.as_view())
urlpatterns += p("despachos/", DespachoListCreateView.as_view())
