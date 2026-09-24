import tempfile
from pathlib import Path
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.permissions import PERMISOS_POR_ROL

from decimal import Decimal

from api.models import (
    User, Cliente, ClienteToken, Material, MaterialPlanta, Planta,
    SolicitudCotizacion, SolicitudCotizacionItem, Cotizacion, Pago,
    OrdenSuministro, SolicitudToken,
)

# Los PDFs de las pruebas van a un directorio temporal, no al media/ real.
_TMP_PDFS = Path(tempfile.mkdtemp(prefix="facturacion-test-pdfs-"))


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class TokenVinculacionTest(TestCase):
    """Link de vinculación: el comercial lo genera, el cliente lo llena."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"])
        self.comercial.set_password("x")
        self.comercial.save()
        self.planta_user = User(username="pl", rol="planta", permisos=PERMISOS_POR_ROL["planta"])
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
        MaterialPlanta.objects.create(material=self.material, planta=self.planta, precio_especial=100)

        self.cliente = Cliente.objects.create(nombre="Cliente X", numero_vinculacion="VIN-0001")
        self.solicitud = SolicitudCotizacion.objects.create(
            numero="SC-0001", cliente=self.cliente, creado_por=self.comercial,
        )
        SolicitudCotizacionItem.objects.create(
            solicitud=self.solicitud, material=self.material, cantidad=10,
        )
        self.api = APIClient()

    def _user(self, username, rol):
        u = User(username=username, rol=rol, permisos=PERMISOS_POR_ROL.get(rol, []))
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

    def test_pagos_parciales_y_rechazo(self):
        cot = self._crear_cotizacion()
        self._decidir_cotizacion(cot["id"], True)
        total = Decimal(Cotizacion.objects.get(id=cot["id"]).total)

        self._login(self.comercial)
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 1000}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        primer_pago = r.json()["id"]
        self.assertEqual(r.json()["estado"], "pendiente")

        # Un abono más que se pase de lo que falta: no.
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": str(total)}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

        self._login(self.financiera)
        r = self.api.post(f"/api/v1/pagos/{primer_pago}/aprobar/",
                          {"aprobar": False, "motivo": "Comprobante ilegible"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

        # Rechazado no cuenta: ahora sí cabe el total.
        self._login(self.comercial)
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": str(total)}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Pago.objects.filter(cotizacion_id=cot["id"]).count(), 2)

    def test_pago_aprobado_ya_no_crea_la_orden(self):
        cot = self._crear_cotizacion()
        self._decidir_cotizacion(cot["id"], True)
        self._login(self.comercial)
        pago_id = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 1000},
                                format="json").json()["id"]
        self._login(self.financiera)
        r = self.api.post(f"/api/v1/pagos/{pago_id}/aprobar/", {"aprobar": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Cotizacion.objects.get(id=cot["id"]).ordenes_suministro.count(), 0)

    def test_orden_de_compra_queda_por_confirmar(self):
        cot = self._crear_cotizacion()
        self._decidir_cotizacion(cot["id"], True)
        self._login(self.comercial)
        r = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 800,
                                             "tipo": "orden_compra", "referencia": "OC-778"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["estado"], "por_confirmar")
        c = Cotizacion.objects.get(id=cot["id"])
        self.assertTrue(c.habilita_ordenes)
        self.assertEqual(c.total_por_confirmar, Decimal("800"))
        self.assertEqual(c.total_pagado, 0)

        r = self.api.get("/api/v1/pagos/cartera/")
        self.assertEqual(r.status_code, 200, r.content)
        fila = r.json()[0]
        self.assertEqual(Decimal(fila["por_confirmar"]), Decimal("800"))

        # Llega la plata: financiera confirma con el monto recibido.
        self._login(self.financiera)
        oc = Pago.objects.get(cotizacion_id=cot["id"])
        r = self.api.post(f"/api/v1/pagos/{oc.id}/aprobar/", {"aprobar": True, "monto": 600}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        c = Cotizacion.objects.get(id=cot["id"])
        self.assertEqual(c.total_pagado, Decimal("600"))
        self.assertEqual(c.total_por_confirmar, 0)

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
        self.assertEqual(etapa()["etapa"], "pendiente_orden")

        self._login(self.comercial)
        c = Cotizacion.objects.get(id=cot2["id"])
        item = c.items.first()
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": c.id, "planta": item.planta_efectiva.id,
            "items": [{"cotizacion_item": item.id, "cantidad": str(item.cantidad)}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(etapa()["etapa"], "pendiente_notificacion")
        self.api.post(f"/api/v1/ordenes-suministro/{r.json()['id']}/notificar/", {"canales": ["manual"]}, format="json")
        self.assertEqual(etapa()["etapa"], "pendiente_despacho")

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


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class MultiPlantaTest(TestCase):
    """Repartir una cotización entre varias plantas emite una orden por planta."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"]); self.comercial.set_password("x"); self.comercial.save()
        self.aprobador = User(username="apr", rol="aprobador", permisos=PERMISOS_POR_ROL["aprobador"]); self.aprobador.set_password("x"); self.aprobador.save()
        self.financiera = User(username="fin", rol="financiera", permisos=PERMISOS_POR_ROL["financiera"]); self.financiera.set_password("x"); self.financiera.save()

        self.p1 = Planta.objects.create(nombre="Planta Uno")
        self.p2 = Planta.objects.create(nombre="Planta Dos")
        self.material = Material.objects.create(nombre="Triturado 3/4", unidad_medida="m3")
        # Precios distintos a propósito: el reparto debe cobrar el de cada planta.
        MaterialPlanta.objects.create(
            material=self.material, planta=self.p1, precio_especial=100, precio_detal=120)
        MaterialPlanta.objects.create(
            material=self.material, planta=self.p2, precio_especial=150, precio_detal=180)

        self.cliente = Cliente.objects.create(nombre="Cliente X", numero_vinculacion="VIN-0001")
        self.solicitud = SolicitudCotizacion.objects.create(
            numero="SC-0001", cliente=self.cliente, creado_por=self.comercial)
        SolicitudCotizacionItem.objects.create(
            solicitud=self.solicitud, material=self.material, cantidad=100)
        self.api = APIClient()

    def _login(self, u):
        r = self.api.post("/api/v1/auth/login", {"username": u.username, "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def test_reparto_entre_plantas_cobra_el_precio_de_cada_una(self):
        self._login(self.comercial)
        r = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": self.solicitud.id, "planta": self.p1.id,
            "items": [
                {"material": self.material.id, "planta": self.p1.id, "cantidad": 60},
                {"material": self.material.id, "planta": self.p2.id, "cantidad": 40},
            ],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()

        # 60 × 100 + 40 × 150 = 12.000 sin IVA; con 19% = 14.280
        self.assertEqual(Decimal(data["subtotal"]), Decimal("12000.00"))
        self.assertEqual(Decimal(data["iva"]), Decimal("2280.00"))
        self.assertEqual(Decimal(data["total"]), Decimal("14280.00"))
        self.assertEqual(sorted(data["plantas_nombres"]), ["Planta Dos", "Planta Uno"])
        precios = {i["planta_nombre"]: Decimal(i["precio_unitario"]) for i in data["items"]}
        self.assertEqual(precios["Planta Uno"], Decimal("100.00"))
        self.assertEqual(precios["Planta Dos"], Decimal("150.00"))

    def _cotizacion_pagada(self):
        self._login(self.comercial)
        cot = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": self.solicitud.id, "planta": self.p1.id,
            "items": [
                {"material": self.material.id, "planta": self.p1.id, "cantidad": 60},
                {"material": self.material.id, "planta": self.p2.id, "cantidad": 40},
            ],
        }, format="json").json()
        self._login(self.aprobador)
        self.api.post(f"/api/v1/cotizaciones/{cot['id']}/aprobar/", {"aprobar": True}, format="json")
        self._login(self.comercial)
        pago_id = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 5000},
                                format="json").json()["id"]
        self._login(self.financiera)
        self.api.post(f"/api/v1/pagos/{pago_id}/aprobar/", {"aprobar": True}, format="json")
        self._login(self.comercial)
        return Cotizacion.objects.get(id=cot["id"])

    def test_ordenes_manuales_parciales_por_planta(self):
        c = self._cotizacion_pagada()
        linea_p1 = c.items.get(planta=self.p1)
        linea_p2 = c.items.get(planta=self.p2)

        r = self.api.get("/api/v1/ordenes-suministro/por-ordenar/")
        self.assertEqual([x["id"] for x in r.json()], [c.id])

        # Parcial: 25 de los 60 de Planta Uno.
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": c.id, "planta": self.p1.id, "placas_cliente": "SPT880",
            "fecha_suministro": "2026-10-01",
            "items": [{"cotizacion_item": linea_p1.id, "cantidad": 25}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Decimal(r.json()["items"][0]["cantidad"]), Decimal("25"))
        self.assertIn("wa.me", r.json()["whatsapp_url"])

        # Una línea de otra planta no entra en esta orden.
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": c.id, "planta": self.p1.id,
            "items": [{"cotizacion_item": linea_p2.id, "cantidad": 5}],
        }, format="json")
        self.assertEqual(r.status_code, 400)

        # No se puede ordenar más del saldo (quedan 35).
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": c.id, "planta": self.p1.id,
            "items": [{"cotizacion_item": linea_p1.id, "cantidad": 36}],
        }, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": c.id, "planta": self.p1.id,
            "items": [{"cotizacion_item": linea_p1.id, "cantidad": 35}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)

        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": c.id, "planta": self.p2.id,
            "items": [{"cotizacion_item": linea_p2.id, "cantidad": 40}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(OrdenSuministro.objects.filter(cotizacion=c).count(), 3)

        # Todo ordenado: ya no aparece por ordenar.
        self.assertEqual(self.api.get("/api/v1/ordenes-suministro/por-ordenar/").json(), [])

    def test_sin_pago_no_hay_orden(self):
        self._login(self.comercial)
        cot = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": self.solicitud.id, "planta": self.p1.id,
            "items": [{"material": self.material.id, "cantidad": 10}],
        }, format="json").json()
        self._login(self.aprobador)
        self.api.post(f"/api/v1/cotizaciones/{cot['id']}/aprobar/", {"aprobar": True}, format="json")
        self._login(self.comercial)
        item = Cotizacion.objects.get(id=cot["id"]).items.first()
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": cot["id"], "planta": self.p1.id,
            "items": [{"cotizacion_item": item.id, "cantidad": 10}],
        }, format="json")
        self.assertEqual(r.status_code, 400)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class LinkDePedidosTest(TestCase):
    """El cliente arma su propia solicitud de cotización desde un link."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"]); self.comercial.set_password("x"); self.comercial.save()
        self.planta = Planta.objects.create(nombre="Planta Uno")
        self.material = Material.objects.create(nombre="Triturado 3/4", unidad_medida="m3")
        self.inactivo = Material.objects.create(nombre="Descontinuado", unidad_medida="m3", activo=False)
        self.cliente = Cliente.objects.create(nombre="Cliente X", numero_vinculacion="VIN-0001")
        self.api = APIClient()
        self.pub = APIClient()

    def _login(self):
        r = self.api.post("/api/v1/auth/login", {"username": "com", "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def _token(self):
        self._login()
        r = self.api.post("/api/v1/solicitud-tokens/", {"cliente": self.cliente.id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_el_link_sirve_varias_veces(self):
        tok = self._token()["token"]

        r = self.pub.get(f"/api/v1/publico/solicitud/{tok}/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["cliente_nombre"], "Cliente X")
        # El catálogo no expone precios ni materiales inactivos.
        nombres = [m["nombre"] for m in r.json()["materiales"]]
        self.assertIn("Triturado 3/4", nombres)
        self.assertNotIn("Descontinuado", nombres)
        self.assertNotIn("precio_unitario", r.json()["materiales"][0])

        for _ in range(2):
            r = self.pub.post(f"/api/v1/publico/solicitud/{tok}/", {
                "items": [{"material": self.material.id, "cantidad": 50}],
                "notas": "Para la obra del norte",
            }, format="json")
            self.assertEqual(r.status_code, 201, r.content)

        self.assertEqual(SolicitudCotizacion.objects.filter(cliente=self.cliente).count(), 2)
        numeros = sorted(s.numero for s in SolicitudCotizacion.objects.all())
        self.assertEqual(numeros, ["SC-0001", "SC-0002"])

        token = SolicitudToken.objects.get(token=tok)
        self.assertEqual(token.usos, 2)

    def test_un_link_vivo_por_cliente(self):
        primero = self._token()
        r = self.api.post("/api/v1/solicitud-tokens/", {"cliente": self.cliente.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["token"], primero["token"])

    def test_revocar_cierra_el_link(self):
        tok = self._token()
        r = self.api.delete(f"/api/v1/solicitud-tokens/{tok['id']}/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["estado"], "revocado")

        r = self.pub.get(f"/api/v1/publico/solicitud/{tok['token']}/")
        self.assertEqual(r.status_code, 410, r.content)
        r = self.pub.post(f"/api/v1/publico/solicitud/{tok['token']}/",
                          {"items": [{"material": self.material.id, "cantidad": 5}]}, format="json")
        self.assertEqual(r.status_code, 410, r.content)

    def test_validaciones_del_pedido(self):
        tok = self._token()["token"]
        base = f"/api/v1/publico/solicitud/{tok}/"

        self.assertEqual(self.pub.post(base, {"items": []}, format="json").status_code, 400)
        self.assertEqual(self.pub.post(
            base, {"items": [{"material": self.material.id, "cantidad": 0}]}, format="json").status_code, 400)
        self.assertEqual(self.pub.post(
            base, {"items": [{"material": self.inactivo.id, "cantidad": 5}]}, format="json").status_code, 400)
        # Nada se creó a medias.
        self.assertEqual(SolicitudCotizacion.objects.count(), 0)

        self.assertEqual(self.pub.get("/api/v1/publico/solicitud/nada/").status_code, 404)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class TarifasEIvaTest(TestCase):
    """Dos listas de precios por planta e IVA discriminado."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"])
        self.comercial.set_password("x")
        self.comercial.save()

        self.planta = Planta.objects.create(nombre="Planta de prueba")
        self.material = Material.objects.create(nombre="Piedra de prueba", unidad_medida="m3")
        # Como en la lista real: especial 44.000, detal 54.000.
        MaterialPlanta.objects.create(
            material=self.material, planta=self.planta,
            precio_especial=Decimal("44000"), precio_detal=Decimal("54000"),
        )
        # Catarina no maneja tarifa de detal.
        self.sin_detal = Material.objects.create(nombre="Base de prueba", unidad_medida="m3")
        MaterialPlanta.objects.create(
            material=self.sin_detal, planta=self.planta,
            precio_especial=Decimal("43000"), precio_detal=None,
        )
        self.api = APIClient()
        r = self.api.post("/api/v1/auth/login", {"username": "com", "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def _cotizar(self, tipo_precio_cliente, material=None):
        cliente = Cliente.objects.create(
            nombre=f"Cliente {tipo_precio_cliente}", tipo_precio=tipo_precio_cliente,
            numero_vinculacion=f"VIN-{tipo_precio_cliente}",
        )
        material = material or self.material
        solicitud = SolicitudCotizacion.objects.create(
            numero=f"SC-{tipo_precio_cliente}-{material.id}", cliente=cliente, creado_por=self.comercial)
        SolicitudCotizacionItem.objects.create(solicitud=solicitud, material=material, cantidad=10)
        r = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": solicitud.id, "planta": self.planta.id,
            "items": [{"material": material.id, "cantidad": 10}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_la_tarifa_sale_del_cliente(self):
        especial = self._cotizar("especial")
        self.assertEqual(especial["tipo_precio"], "especial")
        self.assertEqual(Decimal(especial["items"][0]["precio_unitario"]), Decimal("44000.00"))
        self.assertEqual(Decimal(especial["subtotal"]), Decimal("440000.00"))

        detal = self._cotizar("detal")
        self.assertEqual(detal["tipo_precio"], "detal")
        self.assertEqual(Decimal(detal["items"][0]["precio_unitario"]), Decimal("54000.00"))
        self.assertEqual(Decimal(detal["subtotal"]), Decimal("540000.00"))

    def test_sin_tarifa_detal_se_usa_la_especial(self):
        cot = self._cotizar("detal", material=self.sin_detal)
        self.assertEqual(Decimal(cot["items"][0]["precio_unitario"]), Decimal("43000.00"))

    def test_iva_discriminado(self):
        cot = self._cotizar("especial")
        self.assertEqual(Decimal(cot["iva_porcentaje"]), Decimal("19.00"))
        self.assertEqual(Decimal(cot["subtotal"]), Decimal("440000.00"))
        self.assertEqual(Decimal(cot["iva"]), Decimal("83600.00"))
        self.assertEqual(Decimal(cot["total"]), Decimal("523600.00"))

    def test_catalogo_real_se_carga_y_es_idempotente(self):
        from django.core.management import call_command
        for _ in range(2):
            call_command("cargar_precios", verbosity=0)

        # 6 del catálogo + la de esta prueba.
        self.assertEqual(Planta.objects.filter(activa=True).count(), 7)
        self.assertEqual(MaterialPlanta.objects.filter(planta__nombre="Planta Portobelo").count(), 18)

        # Un precio conocido de la lista: piedra filtro en Portobelo.
        mp = MaterialPlanta.objects.get(
            planta__nombre="Planta Portobelo", material__nombre="Piedra filtro")
        self.assertEqual(mp.precio_especial, Decimal("44000.00"))
        self.assertEqual(mp.precio_detal, Decimal("54000.00"))
        self.assertEqual(mp.precio("especial"), Decimal("44000.00"))
        self.assertEqual(mp.precio("detal"), Decimal("54000.00"))

        # Catarina no tiene tarifa de detal: cae a la especial.
        catarina = MaterialPlanta.objects.get(
            planta__nombre="Planta Catarina", material__nombre="Base granular tipo INVIAS")
        self.assertIsNone(catarina.precio_detal)
        self.assertEqual(catarina.precio("detal"), Decimal("43000.00"))


class PlantasActivasTest(TestCase):
    """Las plantas dadas de baja no deben ofrecerse al cotizar."""

    def setUp(self):
        self.admin = User(username="adm", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"], is_admin=True)
        self.admin.set_password("x")
        self.admin.save()
        Planta.objects.create(nombre="Planta Real", activa=True)
        Planta.objects.create(nombre="Planta De Ejemplo", activa=False)
        self.api = APIClient()
        r = self.api.post("/api/v1/auth/login", {"username": "adm", "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def test_por_defecto_solo_activas(self):
        r = self.api.get("/api/v1/plantas/")
        nombres = [p["nombre"] for p in r.json()]
        self.assertEqual(nombres, ["Planta Real"])

    def test_el_admin_puede_pedirlas_todas(self):
        r = self.api.get("/api/v1/plantas/", {"todas": 1})
        nombres = sorted(p["nombre"] for p in r.json())
        self.assertEqual(nombres, ["Planta De Ejemplo", "Planta Real"])

    def test_se_puede_reactivar(self):
        planta = Planta.objects.get(nombre="Planta De Ejemplo")
        r = self.api.patch(f"/api/v1/plantas/{planta.id}/", {"activa": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(self.api.get("/api/v1/plantas/").json()), 2)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS, COTIZACION_CONSECUTIVO_INICIAL=159)
class FormatosRealesTest(TestCase):
    """Cotización FR-GC-08, orden de suministro y control de despacho de materiales."""

    def setUp(self):
        from datetime import date as _d
        self._date = _d
        self.comercial = User(username="paola", nombre="Paola Andrea Posso", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"],
                              cargo="Asesora comercial", telefono="3128342898")
        self.comercial.set_password("x")
        self.comercial.save()
        self.aprobador = User(username="apr", rol="aprobador", permisos=PERMISOS_POR_ROL["aprobador"]); self.aprobador.set_password("x"); self.aprobador.save()
        self.financiera = User(username="fin", rol="financiera", permisos=PERMISOS_POR_ROL["financiera"]); self.financiera.set_password("x"); self.financiera.save()
        self.planta_user = User(username="pla", rol="planta", permisos=PERMISOS_POR_ROL["planta"], nombre="Valentina Guzmán",
                                cargo="Asistente administrativa")
        self.planta_user.set_password("x")
        self.planta_user.save()

        self.planta = Planta.objects.create(nombre="Planta Corinto")
        self.material = Material.objects.create(nombre="Sub base granular", unidad_medida="m3")
        MaterialPlanta.objects.create(material=self.material, planta=self.planta,
                                      precio_especial=Decimal("41000"), precio_detal=Decimal("44000"))
        self.cliente = Cliente.objects.create(
            nombre="Montevilla Construcciones SAS", nit="901571869-0",
            direccion="Av de las Americas 55 07", telefono="6063330393", numero_vinculacion="VIN-0001")
        self.api = APIClient()

    def _login(self, u):
        r = self.api.post("/api/v1/auth/login", {"username": u.username, "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def _hasta_orden(self, cantidad=100):
        """Solicitud → cotización → aprobación → pago aprobado. Devuelve la orden."""
        self._login(self.comercial)
        sol = self.api.post("/api/v1/solicitudes-cotizacion/", {
            "cliente": self.cliente.id, "obra": "Villa Bosque Nativo",
            "items": [{"material": self.material.id, "cantidad": cantidad}],
        }, format="json").json()
        cot = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": sol["id"], "planta": self.planta.id,
            "items": [{"material": self.material.id, "cantidad": cantidad}],
        }, format="json").json()
        self._login(self.aprobador)
        self.api.post(f"/api/v1/cotizaciones/{cot['id']}/aprobar/", {"aprobar": True}, format="json")
        self._login(self.comercial)
        pago = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": cot["total"]}, format="json").json()
        self._login(self.financiera)
        self.api.post(f"/api/v1/pagos/{pago['id']}/aprobar/", {"aprobar": True}, format="json")
        self._login(self.comercial)
        item = Cotizacion.objects.get(id=cot["id"]).items.first()
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": cot["id"], "planta": self.planta.id,
            "items": [{"cotizacion_item": item.id, "cantidad": cantidad}],
        }, format="json")
        assert r.status_code == 201, r.content
        return cot, OrdenSuministro.objects.get(id=r.json()["id"])

    def test_numeracion_por_anio_sigue_el_consecutivo_real(self):
        cot, _ = self._hasta_orden()
        anio = timezone.localdate().year
        self.assertEqual(cot["numero"], f"160-{anio}")

        from services.pdf_service import numero_cotizacion_formal
        self.assertEqual(numero_cotizacion_formal("159-2026"), "159-2.026")

    def test_pdf_de_cotizacion_se_genera(self):
        cot, _ = self._hasta_orden()
        self._login(self.comercial)
        r = self.api.get(f"/api/v1/cotizaciones/{cot['id']}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(b"".join(r.streaming_content).startswith(b"%PDF"))

    def test_obra_y_placas_llegan_a_la_orden(self):
        _, orden = self._hasta_orden()
        self._login(self.comercial)
        r = self.api.patch(f"/api/v1/ordenes-suministro/{orden.id}/", {
            "fecha_suministro": "2026-07-24", "placas_cliente": "spt880, wmb006",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["obra"], "Villa Bosque Nativo")
        self.assertEqual(r.json()["placas_cliente"], "spt880, wmb006")

        from api.views.orden_suministro_views import _datos_pdf
        orden.refresh_from_db()
        datos = _datos_pdf(orden)
        self.assertEqual(datos["placas_cliente"], ["SPT880", "WMB006"])
        self.assertEqual(datos["autoriza"]["nombre"], "Paola Andrea Posso")

    def test_la_orden_no_la_edita_cualquiera(self):
        _, orden = self._hasta_orden()
        self._login(self.aprobador)
        r = self.api.patch(f"/api/v1/ordenes-suministro/{orden.id}/", {"placas_cliente": "X"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_control_de_despachos_valoriza_con_el_precio_cotizado(self):
        _, orden = self._hasta_orden(cantidad=100)
        self._login(self.planta_user)
        for fecha, consecutivo, placa, cant in [
            ("2026-06-23", "758812", "WMB006", "16.04"),
            ("2026-07-03", "759304", "SPT880", "15.50"),
        ]:
            r = self.api.post("/api/v1/despachos/", {
                "orden_suministro": orden.id, "fecha": fecha, "consecutivo": consecutivo,
                "placa_vehiculo": placa, "items": [{"material": self.material.id, "cantidad": cant}],
            }, format="json")
            self.assertEqual(r.status_code, 201, r.content)

        from api.views.control_despachos_views import armar_control
        c = armar_control(self.cliente)
        self.assertEqual([f["consecutivo"] for f in c["filas"]], ["758812", "759304"])
        self.assertEqual(c["filas"][0]["obra"], "Villa Bosque Nativo")
        self.assertEqual(c["filas"][0]["valor_unitario"], Decimal("41000.00"))
        # 16,04 × 41.000 = 657.640 y 15,50 × 41.000 = 635.500
        self.assertEqual(c["subtotal"], Decimal("1293140"))
        self.assertEqual(c["iva"], Decimal("245697"))
        self.assertEqual(c["total_cantidad"], Decimal("31.54"))
        self.assertEqual(c["comercial"], self.comercial)

        # Filtro por fechas.
        solo_julio = armar_control(self.cliente, desde=self._date(2026, 7, 1))
        self.assertEqual(len(solo_julio["filas"]), 1)

        r = self.api.get("/api/v1/control-despachos/pdf/", {"cliente": self.cliente.id})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))


class DatosDeEjemploTest(TestCase):
    """La migración 0009 apaga los datos inventados del seed viejo, solo esos."""

    def test_desactiva_solo_los_de_ejemplo(self):
        import importlib
        from django.apps import apps as django_apps
        mig = importlib.import_module("api.migrations.0009_desactivar_datos_de_ejemplo")

        Planta.objects.create(nombre="Planta El Roble")
        Planta.objects.create(nombre="Planta Corinto")
        Material.objects.create(nombre="Recebo")
        Material.objects.create(nombre="Piedra filtro")
        mig.desactivar(django_apps, None)

        self.assertFalse(Planta.objects.get(nombre="Planta El Roble").activa)
        self.assertTrue(Planta.objects.get(nombre="Planta Corinto").activa)
        self.assertFalse(Material.objects.get(nombre="Recebo").activo)
        self.assertTrue(Material.objects.get(nombre="Piedra filtro").activo)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class CotizacionControlTest(TestCase):
    """Precio por línea, planta sin precio, cargos/descuentos y notas elegidas."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial", permisos=PERMISOS_POR_ROL["comercial"], is_admin=True)
        self.comercial.set_password("x")
        self.comercial.save()
        self.con_precio = Planta.objects.create(nombre="Planta Con Precio")
        self.sin_precio = Planta.objects.create(nombre="Planta Sin Precio")
        self.material = Material.objects.create(nombre="Piedra filtro", unidad_medida="m3")
        MaterialPlanta.objects.create(material=self.material, planta=self.con_precio,
                                      precio_especial=Decimal("44000"), precio_detal=Decimal("54000"))
        cliente = Cliente.objects.create(nombre="Cliente", numero_vinculacion="VIN-0001")
        self.solicitud = SolicitudCotizacion.objects.create(numero="SC-0001", cliente=cliente,
                                                            creado_por=self.comercial)
        SolicitudCotizacionItem.objects.create(solicitud=self.solicitud, material=self.material, cantidad=100)
        self.api = APIClient()
        r = self.api.post("/api/v1/auth/login", {"username": "com", "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def _cotizar(self, **extra):
        cuerpo = {"solicitud": self.solicitud.id, "planta": self.con_precio.id,
                  "items": [{"material": self.material.id, "planta": self.con_precio.id, "cantidad": 100}]}
        cuerpo.update(extra)
        return self.api.post("/api/v1/cotizaciones/", cuerpo, format="json")

    def test_planta_sin_precio_se_rechaza_y_no_crea_nada(self):
        r = self._cotizar(items=[{"material": self.material.id, "planta": self.sin_precio.id, "cantidad": 100}])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("no tiene precio", r.json()["detail"])
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_precio_por_linea_especial_detal_o_manual(self):
        r = self._cotizar(items=[
            {"material": self.material.id, "planta": self.con_precio.id, "cantidad": 10, "origen_precio": "detal"},
            {"material": self.material.id, "planta": self.con_precio.id, "cantidad": 10,
             "origen_precio": "especial", "precio_unitario": 1},  # el precio del navegador se ignora
            {"material": self.material.id, "planta": self.sin_precio.id, "cantidad": 10,
             "origen_precio": "manual", "precio_unitario": 50000},
        ])
        self.assertEqual(r.status_code, 201, r.content)
        precios = [(i["origen_precio"], Decimal(i["precio_unitario"])) for i in r.json()["items"]]
        self.assertEqual(precios, [("detal", Decimal("54000.00")), ("especial", Decimal("44000.00")),
                                   ("manual", Decimal("50000.00"))])

    def test_manual_sin_precio_se_rechaza(self):
        r = self._cotizar(items=[{"material": self.material.id, "planta": self.con_precio.id,
                                  "cantidad": 10, "origen_precio": "manual"}])
        self.assertEqual(r.status_code, 400)

    def test_cargos_y_descuentos(self):
        r = self._cotizar(ajustes=[
            {"tipo": "descuento", "modo": "porcentaje", "descripcion": "Descuento comercial", "valor": 10},
            {"tipo": "cargo", "modo": "monto", "descripcion": "Flete", "valor": 200000, "aplica_iva": False},
        ])
        self.assertEqual(r.status_code, 201, r.content)
        c = r.json()
        # 100 × 44.000 = 4.400.000; −10% = −440.000; + flete 200.000 sin IVA
        self.assertEqual(Decimal(c["subtotal_materiales"]), Decimal("4400000.00"))
        self.assertEqual(Decimal(c["subtotal"]), Decimal("4160000.00"))
        # IVA solo sobre lo gravado: (4.400.000 − 440.000) × 19% = 752.400
        self.assertEqual(Decimal(c["iva"]), Decimal("752400.00"))
        self.assertEqual(Decimal(c["total"]), Decimal("4912400.00"))
        self.assertEqual([Decimal(a["valor_calculado"]) for a in c["ajustes"]],
                         [Decimal("-440000.00"), Decimal("200000.00")])

    def test_ajuste_invalido_no_crea_nada(self):
        r = self._cotizar(ajustes=[{"tipo": "descuento", "modo": "porcentaje", "descripcion": "X", "valor": 150}])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_notas_aclaratorias_elegidas(self):
        catalogo = self.api.get("/api/v1/cotizaciones/notas-aclaratorias/").json()
        self.assertTrue(all({"clave", "titulo", "texto"} <= set(n) for n in catalogo))

        r = self._cotizar(notas_aclaratorias=["horario", "clave_inventada"], notas="Entrega en obra\nPago 50/50")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["notas_aclaratorias"], ["horario"])

        from services.notas_cotizacion import elegidas
        self.assertEqual([n["clave"] for n in elegidas(["horario"])], ["horario"])
        self.assertEqual(len(elegidas(None)), len(catalogo))

    def test_quitar_precio_de_una_planta(self):
        r = self.api.delete(f"/api/v1/materiales/{self.material.id}/precios/?planta={self.con_precio.id}")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(MaterialPlanta.objects.filter(planta=self.con_precio).exists())


class GestionUsuariosTest(TestCase):
    """Superusuario, admin y usuarios normales: quién puede crear y tocar a quién."""

    def _user(self, username, **kw):
        kw.setdefault("permisos", ["tablero"])
        u = User(username=username, rol=kw.pop("rol", "comercial"), **kw)
        u.set_password("clave-segura")
        u.save()
        return u

    def setUp(self):
        self.super = self._user("dueno", is_superadmin=True)
        self.admin = self._user("jefe", is_admin=True)
        self.comercial = self._user("vendedor")
        self.api = APIClient()

    def _login(self, username, password="clave-segura"):
        self.api.credentials()
        r = self.api.post("/api/v1/auth/login", {"username": username, "password": password}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def test_superusuario_siempre_es_admin(self):
        self.assertTrue(self.super.is_admin)

    def test_alta_con_clave_temporal_y_primer_ingreso(self):
        self._login("jefe")
        r = self.api.post("/api/v1/users/", {
            "username": "Paola", "password": "temporal123", "rol": "comercial",
            "nombre": "Paola Posso", "cedula": "1.112.000",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["username"], "paola")
        self.assertTrue(r.json()["debe_cambiar_password"])

        self._login("PAOLA", "temporal123")  # sin distinguir mayúsculas
        r = self.api.post("/api/v1/auth/cambiar-password", {"nueva": "corta"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.post("/api/v1/auth/cambiar-password", {"nueva": "definitiva123"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["debe_cambiar_password"])
        # Ya no es primer ingreso: ahora sí pide la actual.
        r = self.api.post("/api/v1/auth/cambiar-password", {"nueva": "otra-clave-1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_no_crea_ni_toca_administradores(self):
        self._login("jefe")
        r = self.api.post("/api/v1/users/", {"username": "otro", "password": "temporal123", "is_admin": True}, format="json")
        self.assertEqual(r.status_code, 403)
        r = self.api.patch(f"/api/v1/users/{self.comercial.id}/", {"is_admin": True}, format="json")
        self.assertEqual(r.status_code, 403)
        r = self.api.patch(f"/api/v1/users/{self.super.id}/", {"nombre": "X"}, format="json")
        self.assertEqual(r.status_code, 403)
        r = self.api.patch(f"/api/v1/users/{self.comercial.id}/", {"rol": "planta"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_superusuario_gestiona_admins(self):
        self._login("dueno")
        r = self.api.patch(f"/api/v1/users/{self.comercial.id}/", {"is_admin": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = self.api.patch(f"/api/v1/users/{self.admin.id}/", {"is_superadmin": True}, format="json")
        self.assertTrue(r.json()["is_admin"] and r.json()["is_superadmin"])

    def test_no_se_queda_sin_superusuario(self):
        self._login("dueno")
        r = self.api.patch(f"/api/v1/users/{self.super.id}/", {"is_superadmin": False}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.delete(f"/api/v1/users/{self.super.id}/")
        self.assertEqual(r.status_code, 400)

    def test_eliminar_solo_sin_documentos(self):
        self._login("dueno")
        Cliente.objects.create(nombre="ACME", creado_por=self.comercial)
        r = self.api.delete(f"/api/v1/users/{self.comercial.id}/")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(User.objects.filter(id=self.comercial.id).exists())

        r = self.api.delete(f"/api/v1/users/{self.admin.id}/")
        self.assertEqual(r.status_code, 204)

    def test_perfil_propio(self):
        self._login("vendedor")
        r = self.api.patch("/api/v1/auth/perfil", {"cedula": "123", "cargo": "Comercial", "is_admin": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["cedula"], "123")
        self.assertFalse(r.json()["is_admin"])

    def test_resumen_tablero(self):
        self._login("vendedor")
        r = self.api.get("/api/v1/tablero/resumen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()["por_mes"]), 6)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS, EMAIL_CONFIGURADO=True,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   UPLOAD_DIR=_TMP_PDFS / "uploads")
class PermisosPlantaYNotificacionTest(TestCase):
    """Permisos por pestaña, plantas asignadas, disponibilidad, aviso a planta y soporte."""

    def _user(self, username, permisos, plantas=()):
        u = User(username=username, rol="comercial", permisos=permisos)
        u.set_password("x")
        u.save()
        u.plantas.set(plantas)
        return u

    def _login(self, u):
        self.api.credentials()
        r = self.api.post("/api/v1/auth/login", {"username": u.username, "password": "x"}, format="json")
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access_token"])

    def setUp(self):
        self.p1 = Planta.objects.create(nombre="Planta Norte", whatsapp="312 834 2898", email="norte@x.com")
        self.p2 = Planta.objects.create(nombre="Planta Sur")
        self.material = Material.objects.create(nombre="Arena", unidad_medida="m3")
        self.mp1 = MaterialPlanta.objects.create(material=self.material, planta=self.p1, precio_especial=100)
        self.mp2 = MaterialPlanta.objects.create(material=self.material, planta=self.p2, precio_especial=100)
        self.admin = self._user("jefe", [])
        self.admin.is_admin = True
        self.admin.save()
        self.despachador = self._user("porteria", ["despachos"], [self.p1])
        self.api = APIClient()

        cliente = Cliente.objects.create(nombre="Cliente Z", numero_vinculacion="VIN-0001")
        sol = SolicitudCotizacion.objects.create(numero="SC-0001", cliente=cliente, obra="Obra 1")
        self.cot = Cotizacion.objects.create(numero="1-2026", solicitud=sol, planta=self.p1, estado="aprobada")
        from api.models import CotizacionItem
        self.l1 = CotizacionItem.objects.create(cotizacion=self.cot, material=self.material, planta=self.p1,
                                                cantidad=50, precio_unitario=100)
        self.l2 = CotizacionItem.objects.create(cotizacion=self.cot, material=self.material, planta=self.p2,
                                                cantidad=10, precio_unitario=100)
        Pago.objects.create(cotizacion=self.cot, monto=1000, estado="aprobado")

    def _orden(self, planta, linea, cantidad):
        self._login(self.admin)
        r = self.api.post("/api/v1/ordenes-suministro/", {
            "cotizacion": self.cot.id, "planta": planta.id,
            "items": [{"cotizacion_item": linea.id, "cantidad": cantidad}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_pestanas_segun_permisos(self):
        self._login(self.despachador)
        self.assertEqual(self.api.get("/api/v1/despachos/").status_code, 200)
        self.assertEqual(self.api.get("/api/v1/ordenes-suministro/").status_code, 200)
        for ruta in ("/api/v1/cotizaciones/", "/api/v1/pagos/", "/api/v1/tablero/", "/api/v1/clientes/"):
            self.assertEqual(self.api.get(ruta).status_code, 403, ruta)
        # Leer el catálogo sí; cambiar precios no.
        self.assertEqual(self.api.get("/api/v1/plantas/").status_code, 200)
        self.assertEqual(self.api.patch(f"/api/v1/plantas/{self.p1.id}/", {"nombre": "X"}, format="json").status_code, 403)

    def test_solo_ve_las_ordenes_de_su_planta(self):
        self._orden(self.p1, self.l1, 20)
        self._orden(self.p2, self.l2, 10)
        self._login(self.despachador)
        r = self.api.get("/api/v1/ordenes-suministro/")
        self.assertEqual([o["planta_nombre"] for o in r.json()], ["Planta Norte"])

    def test_despacho_parcial_y_soporte(self):
        orden = self._orden(self.p1, self.l1, 20)
        self._login(self.despachador)
        r = self.api.post("/api/v1/despachos/", {
            "orden_suministro": orden["id"], "fecha": "2026-10-02",
            "items": [{"material": self.material.id, "cantidad": 12}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        despacho_id = r.json()["id"]
        o = self.api.get(f"/api/v1/ordenes-suministro/{orden['id']}/").json()
        self.assertEqual(Decimal(o["items"][0]["cantidad_despachada"]), Decimal("12"))
        self.assertFalse(o["completamente_despachada"])

        from django.core.files.uploadedfile import SimpleUploadedFile
        archivo = SimpleUploadedFile("tiquete.jpg", b"\xff\xd8\xff fake", content_type="image/jpeg")
        r = self.api.post(f"/api/v1/despachos/{despacho_id}/soporte/", {"file": archivo}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["soporte_path"].endswith(".jpg"))
        self.assertEqual(self.api.get(f"/api/v1/despachos/{despacho_id}/soporte/").status_code, 200)

    def test_notificar_por_whatsapp_y_correo(self):
        from django.core import mail
        orden = self._orden(self.p1, self.l1, 20)
        self.assertTrue(orden["whatsapp_url"].startswith("https://wa.me/573128342898?text="))
        r = self.api.post(f"/api/v1/ordenes-suministro/{orden['id']}/notificar/",
                          {"canales": ["whatsapp", "email"]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["notificada_planta"])
        self.assertEqual(r.json()["canales_notificacion"], ["email", "whatsapp"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["norte@x.com"])
        self.assertEqual(len(mail.outbox[0].attachments), 1)

        # El link del mensaje abre el PDF sin usuario.
        link = r.json()["link_pdf_publico"]
        pub = APIClient()
        resp = pub.get(link.replace("http://testserver", ""))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(pub.get("/api/v1/publico/ordenes/inventado/pdf/").status_code, 404)

    def test_correo_sin_direccion_de_planta(self):
        orden = self._orden(self.p2, self.l2, 5)
        r = self.api.post(f"/api/v1/ordenes-suministro/{orden['id']}/notificar/", {"canales": ["email"]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_disponibilidad_solo_en_sus_plantas(self):
        usuario = self._user("bascula", ["disponibilidad"], [self.p1])
        self._login(usuario)
        r = self.api.patch(f"/api/v1/disponibilidad/materiales/{self.mp1.id}/",
                           {"disponibilidad": "limitada", "cantidad_disponible": "120.5", "disponibilidad_nota": "Llega más el lunes"},
                           format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["disponibilidad"], "limitada")
        r = self.api.patch(f"/api/v1/disponibilidad/materiales/{self.mp2.id}/", {"disponibilidad": "agotada"}, format="json")
        self.assertEqual(r.status_code, 403)
        r = self.api.get("/api/v1/disponibilidad/?mias=1")
        self.assertEqual([p["nombre"] for p in r.json()], ["Planta Norte"])
        # Sin el permiso, no se edita.
        self._login(self.despachador)
        r = self.api.patch(f"/api/v1/disponibilidad/materiales/{self.mp1.id}/", {"disponibilidad": "agotada"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_permisos_invalidos_se_rechazan(self):
        self._login(self.admin)
        r = self.api.post("/api/v1/users/", {"username": "nuevo", "password": "temporal123",
                                             "permisos": ["despachos", "inventado"]}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.post("/api/v1/users/", {"username": "nuevo", "password": "temporal123",
                                             "permisos": ["despachos"], "plantas": [self.p1.id]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["plantas"], [self.p1.id])

    def test_reiniciar_datos_conserva_catalogo_y_usuarios(self):
        from django.core.management import call_command
        self._orden(self.p1, self.l1, 20)
        call_command("reiniciar_datos", "--si", stdout=open("/dev/null", "w"))
        self.assertEqual(Cotizacion.objects.count(), 0)
        self.assertEqual(Cliente.objects.count(), 0)
        self.assertEqual(OrdenSuministro.objects.count(), 0)
        self.assertEqual(MaterialPlanta.objects.count(), 2)
        self.assertTrue(User.objects.filter(username="jefe").exists())


class MigracionOrdenesTest(TestCase):
    """0012: las órdenes viejas reciben token y los ítems de su planta."""

    def test_backfill(self):
        import importlib
        from django.apps import apps as django_apps
        from api.models import CotizacionItem, OrdenSuministroItem
        mig = importlib.import_module("api.migrations.0012_permisos_pagos_parciales_ordenes")
        p1 = Planta.objects.create(nombre="Planta A")
        p2 = Planta.objects.create(nombre="Planta B")
        m = Material.objects.create(nombre="Grava")
        cliente = Cliente.objects.create(nombre="C")
        sol = SolicitudCotizacion.objects.create(numero="SC-1", cliente=cliente)
        cot = Cotizacion.objects.create(numero="1-2026", solicitud=sol, planta=p1, estado="aprobada")
        CotizacionItem.objects.create(cotizacion=cot, material=m, cantidad=7, precio_unitario=1)  # sin planta = p1
        CotizacionItem.objects.create(cotizacion=cot, material=m, planta=p2, cantidad=3, precio_unitario=1)
        orden = OrdenSuministro.objects.create(numero="OS-1", cotizacion=cot, planta=p1)
        mig.tokens_y_items_de_ordenes(django_apps, None)
        self.assertEqual([i.cantidad for i in OrdenSuministroItem.objects.filter(orden=orden)], [Decimal("7")])

        u = User(username="viejo", rol="financiera")
        u.set_password("x")
        u.save()
        mig.permisos_desde_rol(django_apps, None)
        u.refresh_from_db()
        self.assertEqual(u.permisos, ["tablero", "pagos", "aprobar_pagos"])
