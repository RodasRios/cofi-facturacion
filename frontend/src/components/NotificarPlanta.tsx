import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { notificarOrdenSuministro } from "../api/ordenesSuministro";
import { mensajeError } from "../lib/errores";
import type { OrdenSuministro } from "../types";

/**
 * Aviso a planta de una orden de suministro.
 *
 * WhatsApp: abre WhatsApp Web (o la app) con el mensaje ya escrito para el
 * número de la planta; el usuario solo le da enviar desde SU WhatsApp. Se abre
 * en el mismo clic porque el navegador bloquea ventanas abiertas después.
 * Correo: lo manda el servidor, con el PDF adjunto.
 */
export function NotificarPlanta({ orden, compacto = false }: { orden: OrdenSuministro; compacto?: boolean }) {
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: (canal: "whatsapp" | "email" | "manual") => notificarOrdenSuministro(orden.id, [canal]),
    onSuccess: (_o, canal) => {
      qc.invalidateQueries({ queryKey: ["ordenes-suministro"] });
      qc.invalidateQueries({ queryKey: ["tablero"] });
      toast.success(canal === "email" ? `Correo enviado a ${orden.planta_email}` : "Planta notificada");
    },
    onError: e => toast.error(mensajeError(e, "No se pudo notificar")),
  });

  const whatsapp = () => {
    if (orden.whatsapp_url) window.open(orden.whatsapp_url, "_blank", "noopener");
    mut.mutate("whatsapp");
  };

  const sinCorreo = !orden.planta_email
    ? `${orden.planta_nombre} no tiene correo. Configúralo en Plantas y precios.`
    : orden.email_configurado === false ? "El servidor no tiene correo configurado todavía." : "";

  return (
    <div className={`np ${compacto ? "compacto" : ""}`}>
      <button type="button" className="np-wa" onClick={whatsapp} disabled={mut.isPending}
        title={orden.planta_whatsapp ? `Abrir WhatsApp con el mensaje para ${orden.planta_whatsapp}` : "La planta no tiene WhatsApp configurado: podrás elegir el contacto"}>
        <Icon name="chat" size={15} />{compacto ? "" : "WhatsApp"}
      </button>
      <button type="button" className="btn-secondary" onClick={() => mut.mutate("email")}
        disabled={mut.isPending || !!sinCorreo} title={sinCorreo || `Enviar a ${orden.planta_email} con el PDF`}>
        <Icon name="mail" size={15} />{compacto ? "" : "Correo"}
      </button>
      {!orden.notificada_planta && (
        <button type="button" className="btn-ghost" onClick={() => mut.mutate("manual")} disabled={mut.isPending}
          title="Ya se avisó por otro medio (llamada, radio…)">
          <Icon name="done" size={15} />{compacto ? "" : "Ya avisé"}
        </button>
      )}
      <style>{`
        .np { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
        .np-wa {
          display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; font: inherit; font-size: 12.5px;
          border: 1px solid #16a34a; background: #16a34a; color: #fff; cursor: pointer; font-weight: 600;
        }
        .np-wa:hover { background: #15803d; }
        .np.compacto button { padding: 5px 8px; }
      `}</style>
    </div>
  );
}
