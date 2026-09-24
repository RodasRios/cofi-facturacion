"""Notas aclaratorias de la cotización FR-GC-08.

Única fuente del texto: la pantalla de cotización muestra estas notas como
casillas (título + texto desplegable) y el PDF imprime las elegidas, en este
orden. Si cambia el formato en papel, se cambia aquí.

`posicion` las ubica en el documento: las "antes" van antes de la ubicación de
la planta y las "despues" a continuación, como en el formato original.
"""

NOTAS_ACLARATORIAS = [
    {
        "clave": "calidad_invias", "posicion": "antes",
        "titulo": "Calidad según estándares INVIAS",
        "texto": "Los materiales pétreos suministrados por Triturados y Concretos Ltda. son producidos "
                 "bajo los estándares de calidad establecidos por el Instituto Nacional de Vías – INVIAS "
                 "y cumplen con las especificaciones técnicas exigidas por dicha entidad.",
    },
    {
        "clave": "precios_vigentes", "posicion": "antes",
        "titulo": "Precios vigentes y despacho diurno",
        "texto": "El valor de los materiales pétreos fue calculado con base en los precios vigentes a la "
                 "fecha de la cotización y considerando despachos en jornada diurna. Cualquier variación en "
                 "los costos de insumos, combustibles o condiciones operativas, así como requerimientos de "
                 "despacho en jornada nocturna, podrá generar ajustes en los valores cotizados, previa "
                 "validación por parte de Triturados y Concretos Ltda.",
    },
    {
        "clave": "deducciones", "posicion": "antes",
        "titulo": "Sin deducciones del sector público",
        "texto": "La presente oferta no contempla deducciones propias del sector público. Los valores "
                 "cotizados fueron estructurados considerando únicamente los descuentos de ley de carácter "
                 "general, tales como la retención en la fuente por concepto de compras. Cualquier deducción "
                 "adicional que aplique según la naturaleza del contratante deberá ser asumida por el cliente "
                 "o ajustada en la facturación correspondiente.",
    },
    {
        "clave": "cargue_transporte", "posicion": "antes",
        "titulo": "Incluye cargue; transporte a cargo del cliente",
        "texto": "El valor del material incluye el cargue en la volqueta en planta. El transporte será "
                 "responsabilidad del cliente, salvo acuerdo expreso en contrario.",
    },
    {
        "clave": "programacion", "posicion": "antes",
        "titulo": "Programar el pedido con 8 días",
        "texto": "El pedido de material deberá programarse con una anticipación mínima de ocho (8) días "
                 "calendario y el despacho se realizará siempre y cuando la planta se encuentre habilitada "
                 "para labores operativas.",
    },
    {
        "clave": "tiempos_cargue", "posicion": "antes",
        "titulo": "Tiempos de cargue variables",
        "texto": "Los tiempos de cargue podrán variar de acuerdo con la demanda y las condiciones "
                 "operativas de la planta.",
    },
    {
        "clave": "muestra", "posicion": "antes",
        "titulo": "Verificar cubicaje y retirar muestra",
        "texto": "Se recomienda al cliente verificar el cubicaje de la volqueta en planta y retirar muestra "
                 "del material para la realización de los ensayos correspondientes.",
    },
    {
        "clave": "responsabilidad", "posicion": "antes",
        "titulo": "Sin responsabilidad tras salir de planta",
        "texto": "Triturados y Concretos Ltda. no se hace responsable por daños, pérdidas o alteraciones "
                 "del material una vez este haya sido cargado en la volqueta y haya salido de planta.",
    },
    {
        "clave": "retiro_4_meses", "posicion": "antes",
        "titulo": "Retiro dentro de los 4 meses",
        "texto": "El retiro del material deberá efectuarse dentro de los cuatro (4) meses siguientes a la "
                 "fecha de pago. Vencido dicho plazo, el material pendiente de despacho quedará sujeto a "
                 "los precios y condiciones vigentes al momento del retiro.",
    },
    {
        "clave": "horario", "posicion": "despues",
        "titulo": "Horario de planta",
        "texto": "<b>HORARIO DE PLANTA:</b> El horario de despacho de la planta es de lunes a jueves de 7am "
                 "a 3:30 pm, viernes de 7 am a 2:30 pm, sábados de 7 am a 10:30 am, domingos y festivos no "
                 "hay servicio de despacho.",
    },
    {
        "clave": "documentacion", "posicion": "despues",
        "titulo": "Documentación ambiental y de calidad",
        "texto": "La documentación ambiental y de calidad será entregada una vez exista un acuerdo "
                 "comercial formalizado.",
    },
    {
        "clave": "sin_devoluciones", "posicion": "despues",
        "titulo": "Sin devoluciones de dinero",
        "texto": "Una vez realizado el pago, Triturados y Concretos Ltda. no realizará devoluciones de "
                 "dinero por saldos a favor. Dichos saldos serán reconocidos mediante la entrega de "
                 "materiales, de forma proporcional al valor pendiente de compensar.",
    },
    {
        "clave": "cubicaje", "posicion": "despues",
        "titulo": "Verificar cubicaje de la volqueta",
        "texto": "Se recomienda verificar el cubicaje de la volqueta en planta con el fin de evitar "
                 "diferencias en las cantidades de material entregadas.",
    },
    {
        "clave": "variacion_precios", "posicion": "despues",
        "titulo": "Precios sujetos a variación",
        "texto": "Los precios aquí estipulados podrán presentar variaciones en función de las condiciones "
                 "del mercado, costos de insumos y condiciones operativas, sin previo aviso.",
    },
]

CLAVES = [n["clave"] for n in NOTAS_ACLARATORIAS]


def elegidas(claves):
    """Notas a imprimir, en el orden del formato. `None` = todas."""
    if claves is None:
        return list(NOTAS_ACLARATORIAS)
    pedidas = set(claves)
    return [n for n in NOTAS_ACLARATORIAS if n["clave"] in pedidas]
