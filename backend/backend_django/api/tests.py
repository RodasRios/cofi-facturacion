import tempfile
from pathlib import Path
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import (
    User, Cliente, ClienteToken, Material, MaterialPlanta, Planta,
    SolicitudCotizacion, SolicitudCotizacionItem, Cotizacion, Pago,
)

# Los PDFs de las pruebas van a un directorio temporal, no al media/ real.
_TMP_PDFS = Path(tempfile.mkdtemp(prefix="facturacion-test-pdfs-"))


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class TokenVinculacionTest(TestCase):
    """Link de vinculación: el comercial lo genera, el cliente lo llena."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial")
        self.comercial.set_password("x")
        self.comercial.save()
        self.planta_user = User(username="pl", rol="planta")
        self.planta_user.set_password("x")
        self.planta_user.save()
        self.api = APIClient()

    def _login(self, u):
        r = self.api.post("/api/v1/auth/login", {"username": u.username, "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def test_flujo_completo(self):
        self._login(self.comercial)
        r = self.api.post("/api/v1/cliente-tokens/", {"etiqueta": "Constructora ABC"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        tok = r.json()["token"]
        self.assertEqual(r.json()["estado"], "activo")
        self.assertEqual(r.json()["dias_validez"], 3)

        pub = APIClient()
        r = pub.get(f"/api/v1/publico/vinculacion/{tok}/")
        self.assertEqual(r.status_code, 200, r.content)

        r = pub.post(f"/api/v1/publico/vinculacion/{tok}/",
                     {"nombre": "Constructora ABC SAS", "nit": "900123", "telefono": "3001234567"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["numero_vinculacion"], "VIN-0001")
        c = Cliente.objects.get(nombre="Constructora ABC SAS")
        self.assertEqual(c.creado_por_id, self.comercial.id)

        # Un solo uso
        r = pub.post(f"/api/v1/publico/vinculacion/{tok}/", {"nombre": "Otro"}, format="json")
        self.assertEqual(r.status_code, 410, r.content)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_vencido_y_revocado(self):
        self._login(self.comercial)
        tok = ClienteToken.objects.create(creado_por=self.comercial,
                                          expira_at=timezone.now() - timedelta(seconds=1))
        pub = APIClient()
        self.assertEqual(pub.get(f"/api/v1/publico/vinculacion/{tok.token}/").status_code, 410)
        self.assertEqual(pub.post(f"/api/v1/publico/vinculacion/{tok.token}/",
                                  {"nombre": "X"}, format="json").status_code, 410)

        t2 = ClienteToken.objects.create(creado_por=self.comercial)
        r = self.api.delete(f"/api/v1/cliente-tokens/{t2.id}/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["estado"], "revocado")
        self.assertEqual(pub.post(f"/api/v1/publico/vinculacion/{t2.token}/",
                                  {"nombre": "X"}, format="json").status_code, 410)

    def test_token_inexistente_y_nombre_obligatorio(self):
        pub = APIClient()
        self.assertEqual(pub.get("/api/v1/publico/vinculacion/nada/").status_code, 404)
        self._login(self.comercial)
        t = ClienteToken.objects.create(creado_por=self.comercial)
        self.assertEqual(pub.post(f"/api/v1/publico/vinculacion/{t.token}/",
                                  {"nombre": ""}, format="json").status_code, 400)

    def test_rol_planta_no_genera_links(self):
        self._login(self.planta_user)
        r = self.api.post("/api/v1/cliente-tokens/", {}, format="json")
        self.assertEqual(r.status_code, 403, r.content)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class ReintentoYTableroTest(TestCase):
    """Las dos flechas de "No" del flujo: rechazar no deja la solicitud muerta."""

    def setUp(self):
        self.comercial = self._user("com", "comercial")
        self.aprobador = self._user("apr", "aprobador")
        self.financiera = self._user("fin", "financiera")

        self.planta = Planta.objects.create(nombre="Planta Uno")
        self.material = Material.objects.create(nombre="Triturado 3/4", unidad_medida="m3")
        MaterialPlanta.objects.create(material=self.material, planta=self.planta, precio_unitario=100)

        self.cliente = Cliente.objects.create(nombre="Cliente X", numero_vinculacion="VIN-0001")
        self.solicitud = SolicitudCotizacion.objects.create(
            numero="SC-0001", cliente=self.cliente, creado_por=self.comercial,
        )
        SolicitudCotizacionItem.objects.create(
            solicitud=self.solicitud, material=self.material, cantidad=10,
        )
        self.api = APIClient()

    def _user(self, username, rol):
        u = User(username=username, rol=rol)
        u.set_password("x")
        u.save()
        return u

    def _login(self, u):
        r = self.api.post("/api/v1/auth/login", {"username": u.username, "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def _crear_cotizacion(self):
        self._login(self.comercial)
        r = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": self.solicitud.id, "planta": self.planta.id,
            "items": [{"material": self.material.id, "cantidad": 10}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def _decidir_cotizacion(self, cot_id, aprobar, motivo=""):
        self._login(self.aprobador)
        r = self.api.post(f"/api/v1/cotizaciones/{cot_id}/aprobar/",
                          {"aprobar": aprobar, "motivo": motivo}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_cotizacion_rechazada_permite_cotizar_de_nuevo(self):
        primera = self._crear_cotizacion()
        self._decidir_cotizacion(primera["id"], False, "Precio muy alto")

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "en_seguimiento")
        self.assertIsNone(self.solicitud.cotizacion_vigente)

        # El rechazo dejó rastro en la bitácora.
        self._login(self.comercial)
        r = self.api.get(f"/api/v1/solicitudes-cotizacion/{self.solicitud.id}/seguimientos/")
        tipos = [s["tipo"] for s in r.json()]
        self.assertIn("cotizacion_rechazada", tipos)

        # Y se puede armar otra sobre la misma solicitud.
        segunda = self._crear_cotizacion()
        self.assertNotEqual(segunda["id"], primera["id"])
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "cotizada")
        self.assertEqual(self.solicitud.cotizacion_vigente.id, segunda["id"])

    def test_no_se_pueden_tener_dos_cotizaciones_vivas(self):
        self._crear_cotizacion()
        self._login(self.comercial)
        r = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": self.solicitud.id, "planta": self.planta.id,
            "items": [{"material": self.material.id, "cantidad": 5}],
        }, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self.solicitud.cotizaciones.count(), 1)

    def test_pago_rechazado_permite_registrar_otro(self):
        cot = self._crear_cotizacion()
        self._decidir_cotizacion(cot["id"], True)

        self._login(self.comercial)
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 1000}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        primer_pago = r.json()["id"]

        # Con un pago pendiente no se puede registrar otro.
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 1000}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

        self._login(self.financiera)
        r = self.api.post(f"/api/v1/pagos/{primer_pago}/aprobar/",
                          {"aprobar": False, "motivo": "Comprobante ilegible"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

        # Rechazado: ahora sí se puede subir otro sobre la misma cotización.
        self._login(self.comercial)
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 1000}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Pago.objects.filter(cotizacion_id=cot["id"]).count(), 2)

        cotizacion = Cotizacion.objects.get(id=cot["id"])
        self.assertEqual(cotizacion.pago_vigente.id, r.json()["id"])

    def test_pago_aprobado_genera_orden_una_sola_vez(self):
        cot = self._crear_cotizacion()
        self._decidir_cotizacion(cot["id"], True)

        self._login(self.comercial)
        pago_id = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 1000},
                                format="json").json()["id"]
        self._login(self.financiera)
        r = self.api.post(f"/api/v1/pagos/{pago_id}/aprobar/", {"aprobar": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

        cotizacion = Cotizacion.objects.get(id=cot["id"])
        self.assertTrue(hasattr(cotizacion, "orden_suministro"))

    def test_tablero_reporta_la_etapa_correcta(self):
        def etapa():
            self._login(self.comercial)
            r = self.api.get("/api/v1/tablero/")
            self.assertEqual(r.status_code, 200, r.content)
            fila = next(f for f in r.json() if f["numero"] == "SC-0001")
            return fila

        self.assertEqual(etapa()["etapa"], "pendiente_cotizacion")

        cot = self._crear_cotizacion()
        self.assertEqual(etapa()["etapa"], "pendiente_aprobacion")

        self._decidir_cotizacion(cot["id"], False, "No")
        f = etapa()
        self.assertEqual(f["etapa"], "en_seguimiento")
        self.assertEqual(f["cotizaciones_rechazadas"], 1)

        cot2 = self._crear_cotizacion()
        self._decidir_cotizacion(cot2["id"], True)
        self.assertEqual(etapa()["etapa"], "pendiente_pago")

        self._login(self.comercial)
        pago_id = self.api.post("/api/v1/pagos/", {"cotizacion": cot2["id"], "monto": 1000},
                                format="json").json()["id"]
        self.assertEqual(etapa()["etapa"], "pendiente_aprobacion_pago")

        self._login(self.financiera)
        self.api.post(f"/api/v1/pagos/{pago_id}/aprobar/", {"aprobar": True}, format="json")
        self.assertEqual(etapa()["etapa"], "pendiente_notificacion")

    def test_nota_de_seguimiento_manual(self):
        self._login(self.comercial)
        r = self.api.post(f"/api/v1/solicitudes-cotizacion/{self.solicitud.id}/seguimientos/",
                          {"texto": "El cliente pidió rebaja"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["tipo"], "nota")
        self.assertEqual(r.json()["usuario_username"], "com")

        r = self.api.post(f"/api/v1/solicitudes-cotizacion/{self.solicitud.id}/seguimientos/",
                          {"texto": "   "}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
