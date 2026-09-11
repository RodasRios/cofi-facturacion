import tempfile
from pathlib import Path
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

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

        # Una sola planta en la cotización ⇒ una sola orden.
        cotizacion = Cotizacion.objects.get(id=cot["id"])
        self.assertEqual(cotizacion.ordenes_suministro.count(), 1)

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


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class MultiPlantaTest(TestCase):
    """Repartir una cotización entre varias plantas emite una orden por planta."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial"); self.comercial.set_password("x"); self.comercial.save()
        self.aprobador = User(username="apr", rol="aprobador"); self.aprobador.set_password("x"); self.aprobador.save()
        self.financiera = User(username="fin", rol="financiera"); self.financiera.set_password("x"); self.financiera.save()

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

    def test_una_orden_por_planta_con_solo_sus_items(self):
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
        pago_id = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 12000},
                                format="json").json()["id"]
        self._login(self.financiera)
        r = self.api.post(f"/api/v1/pagos/{pago_id}/aprobar/", {"aprobar": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

        ordenes = OrdenSuministro.objects.filter(cotizacion_id=cot["id"])
        self.assertEqual(ordenes.count(), 2)

        r = self.api.get("/api/v1/ordenes-suministro/")
        por_planta = {o["planta_nombre"]: o for o in r.json()}
        self.assertEqual(len(por_planta["Planta Uno"]["items"]), 1)
        self.assertEqual(Decimal(por_planta["Planta Uno"]["items"][0]["cantidad"]), Decimal("60.00"))
        self.assertEqual(Decimal(por_planta["Planta Dos"]["items"][0]["cantidad"]), Decimal("40.00"))

    def test_una_sola_planta_sigue_generando_una_orden(self):
        """El comportamiento de siempre: sin planta por ítem, todo sale de la de la cotización."""
        self._login(self.comercial)
        cot = self.api.post("/api/v1/cotizaciones/", {
            "solicitud": self.solicitud.id, "planta": self.p1.id,
            "items": [{"material": self.material.id, "cantidad": 100}],
        }, format="json").json()
        self.assertEqual(cot["plantas_nombres"], ["Planta Uno"])

        self._login(self.aprobador)
        self.api.post(f"/api/v1/cotizaciones/{cot['id']}/aprobar/", {"aprobar": True}, format="json")
        self._login(self.comercial)
        pago_id = self.api.post("/api/v1/pagos/", {"cotizacion": cot["id"], "monto": 10000},
                                format="json").json()["id"]
        self._login(self.financiera)
        self.api.post(f"/api/v1/pagos/{pago_id}/aprobar/", {"aprobar": True}, format="json")

        self.assertEqual(OrdenSuministro.objects.filter(cotizacion_id=cot["id"]).count(), 1)


@override_settings(GENERATED_PDF_DIR=_TMP_PDFS)
class LinkDePedidosTest(TestCase):
    """El cliente arma su propia solicitud de cotización desde un link."""

    def setUp(self):
        self.comercial = User(username="com", rol="comercial"); self.comercial.set_password("x"); self.comercial.save()
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
        self.comercial = User(username="com", rol="comercial")
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
