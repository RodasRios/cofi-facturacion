from django.urls import path
from api.views.auth_views import LoginView, MeView, UserFirmaView
from api.views.user_views import UserListCreateView, UserDetailView
from api.views.planta_views import PlantaListCreateView, PlantaDetailView
from api.views.material_views import MaterialListCreateView, MaterialDetailView, MaterialPrecioView
from api.views.cliente_views import ClienteListCreateView, ClienteDetailView, ClienteVinculacionView
from api.views.solicitud_views import SolicitudCotizacionListCreateView, SolicitudCotizacionDetailView
from api.views.cotizacion_views import (
    CotizacionListCreateView, CotizacionDetailView, CotizacionAprobarView, CotizacionPdfView,
)
from api.views.pago_views import PagoListCreateView, PagoComprobanteUploadView, PagoAprobarView
from api.views.orden_suministro_views import (
    OrdenSuministroListView, OrdenSuministroDetailView, OrdenSuministroNotificarView, OrdenSuministroPdfView,
)
from api.views.despacho_views import DespachoListCreateView, DespachoDetailView, DespachoPdfView


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

# Clientes
urlpatterns += p("clientes/<int:cliente_id>/vinculacion/", ClienteVinculacionView.as_view())
urlpatterns += p("clientes/<int:cliente_id>/", ClienteDetailView.as_view())
urlpatterns += p("clientes/", ClienteListCreateView.as_view())

# Solicitudes de cotización
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

# Despachos (Control de Despacho y Recibo de Material)
urlpatterns += p("despachos/<int:despacho_id>/pdf/", DespachoPdfView.as_view())
urlpatterns += p("despachos/<int:despacho_id>/", DespachoDetailView.as_view())
urlpatterns += p("despachos/", DespachoListCreateView.as_view())
