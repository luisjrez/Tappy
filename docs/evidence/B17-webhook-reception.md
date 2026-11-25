# Evidencia — B17 Recibir y conservar webhook válido

Ticket: [#25](https://github.com/luisjrez/Tappy/issues/25) · Historia: [H5 #5](https://github.com/luisjrez/Tappy/issues/5) · Protocolo: [TICKET_QUALITY_PROTOCOL](../planning/TICKET_QUALITY_PROTOCOL.md) · Manifiesto: [B17-webhook-reception.toml](B17-webhook-reception.toml)

> Verificado con eventos sintéticos firmados localmente según la especificación de Standard Webhooks y un secreto de prueba generado por ejecución. **No se recibió ningún webhook real de pey** (sin integración real demostrada; la forma exacta de cada evento de pey se valida al aplicarlo en B18 y de extremo a extremo en B35).

## Revisiones y escenario

- Ticket, UC/AC/TC y comprobación: B17-UC01–UC03, B17-AC01–AC03, B17-TC01–TC03, B17-VC01.
- Modalidad: **resultado inicial** (endpoint nuevo). Nuevo contrato `webhook-pey-not-configured` (503) aprobado en `bc000f7`; los demás sin diferencias. Cambio esperado en un test existente: la lista fija de rutas POST públicas incluye `/webhooks/pey`.
- Base: rama B16 (PR #72), stack #68 (H4 → H5). Revisiones: candidato `bc000f7` → `b553a22` (la VC01 descubrió que el secreto configurado impedía arrancar la app; ver TDD).
- Entorno: macOS, Colima + Compose (Postgres 18), Python 3.14.8. Fecha: 2026-11-24. Ejecutor: sesión local de desarrollo del autor del PR.

## Diseño

- `POST /webhooks/pey` (sin sesión de operador; la confianza viene de la firma del proveedor), en el orden de `docs/02-arquitectura.md` §9: limitar tamaño (`TAPPY_WEBHOOK_MAX_BODY_BYTES`, 256 KiB por defecto; `413`) → conservar los bytes originales → verificar Standard Webhooks (`webhook-id`, `webhook-timestamp`, `webhook-signature`; HMAC-SHA256 sobre `id.timestamp.cuerpo` con la clave decodificada de `TAPPY_PEY_WEBHOOK_SECRET` `whsec_…`; comparación en tiempo constante; cualquier entrada `v1` de la lista separada por espacios, para rotación) y la antigüedad (`TAPPY_WEBHOOK_TOLERANCE_SECONDS`, 300; pasado o futuro) → `401` → validar el esquema mínimo (`type` 1–64 y `data` objeto; `400`) → guardar → `204` **después del commit**.
- Separación (Refactor): `tappy.payments.webhooks` solo verifica (sin base de datos); `tappy.payments.events` define `WebhookEvent` y lo guarda; el router orquesta. Nada se aplica al cobro: la aplicación de la evidencia es B18.
- `webhook_events` (migración `0013`): proveedor, `provider_event_id` (`webhook-id`), tipo, **payload crudo** (`bytea`, para volver a verificar), digest SHA-256, `signed_at`, `status` `received` (pendiente de aplicar) y `received_at`; unicidad `(provider, provider_event_id)` con `ON CONFLICT DO NOTHING`, así que una entrega repetida se confirma sin otro registro (el conflicto de contenido con el mismo id es B19).
- Fallo de almacenamiento (`OperationalError`/`InterfaceError`) → `503` «Webhook storage is temporarily unavailable», para que el proveedor reintente; sin secreto configurado → `503`. El downgrade se niega si hay eventos.

## Trazabilidad UC → AC → TC → test

| UC | AC | TC | Test real | Resultado |
| --- | --- | --- | --- | --- |
| B17-UC01 | B17-AC01 | B17-TC01 | `test_valid_event_is_stored_durably_before_success` (`204` y fila confirmada con bytes exactos, id, tipo, digest y `received`); `test_repeated_delivery_is_acknowledged_without_a_second_record`; `test_signatures_from_a_rotated_header_list_are_accepted`; `test_webhook_secret_setting_is_validated_like_any_configuration` | PASS |
| B17-UC02 | B17-AC02 | B17-TC02 | `test_untrusted_deliveries_are_rejected_without_effects` (cuerpo alterado, otro secreto, timestamp viejo o futuro → `401`, 0 filas); `test_missing_or_malformed_headers_are_rejected`; `test_signed_events_with_an_invalid_schema_are_rejected`; `test_oversized_bodies_are_rejected_before_verification`; `test_secret_is_never_echoed` | PASS |
| B17-UC03 | B17-AC03 | B17-TC03 | `test_unavailable_storage_answers_a_temporary_error_and_a_retry_keeps_the_event` (app con Postgres inaccesible → `503`; el reintento con Postgres disponible → `204` y un solo evento); `test_reception_without_a_configured_secret_is_unavailable` | PASS |

## TDD

| Comportamiento | Red | Green |
| --- | --- | --- |
| Recepción, verificación, esquema, límites y almacenamiento | `assert 404 == <HTTPStatus.NO_CONTENT: 204>` / `assert 404 == <HTTPStatus.UNAUTHORIZED: 401>` (no existía la ruta) | Verificación, `WebhookEvent`, router, migración `0013` |
| Secreto configurado (hallado en la VC01) | La app no arrancaba con `TAPPY_PEY_WEBHOOK_SECRET`: `TypeError: Unable to apply constraint 'pattern' … SecretStr`. Test nuevo con validación real: `ValidationError … Input should be a valid string … SecretStr` (los tests usaban `model_copy`, que se salta la validación) | `field_validator` explícito sobre el valor secreto; el fixture usa `Settings.model_validate` |
| Antigüedad | Mutación sin la comprobación de tolerancia: fallan los 2 tests de timestamp | Comprobación `abs(now - timestamp) > tolerance` |
| Cuerpo firmado | Mutación que firma solo `id.timestamp`: 8 tests fallan | El cuerpo forma parte del contenido firmado |

## B17-VC01 — Resultado inicial del webhook

Proceso real `python -m tappy` sobre `b553a22` con un secreto `whsec_` generado para la ejecución; las entregas se firman localmente según Standard Webhooks. La primera petición se hace con un proceso cuyo Postgres es inaccesible (`127.0.0.1:1`); las demás, con el Postgres de desarrollo migrado a `0013_webhook_events`.

| Entrega | Status | Respuesta |
| --- | --- | --- |
| Evento firmado válido `msg_vc01_0001` (DB inaccesible) | 503 | `{"detail":"Webhook storage is temporarily unavailable"}` |
| Mismo evento `msg_vc01_0001` reintentado (DB disponible) | 204 | `(sin cuerpo)` |
| Mismo evento `msg_vc01_0001` repetido | 204 | `(sin cuerpo)` |
| Cuerpo alterado (importe 999.9) con la firma del original | 401 | `{"detail":"Invalid webhook signature"}` |
| Timestamp de hace 10 minutos | 401 | `{"detail":"Invalid webhook signature"}` |
| Firmado, sin `type` | 400 | `{"detail":"Invalid webhook event"}` |

Estructura guardada (saneada: sin cabeceras de firma ni secreto; el payload es sintético):

```json
{
  "provider": "pey",
  "provider_event_id": "msg_vc01_0001",
  "event_type": "codi.qr.payment_received",
  "status": "received",
  "payload_digest": "063f48a03ac9b960c9bdfc5b19683e01e696321442affcdb6819e92ebe145860",
  "payload_bytes": 198,
  "signed_at_present": true,
  "received_at_present": true,
  "payload": {
    "type": "codi.qr.payment_received",
    "timestamp": "2026-11-24T12:00:00Z",
    "data": {
      "codiQrId": "AB12CD34EF",
      "transactionId": "TX-SYNTHETIC-0001",
      "amount": 300.1,
      "metadata": {
        "tappy_reference": "MSPE6WGBSK"
      }
    }
  }
}
```

El secreto aparece 0 veces en los logs de ambos procesos. Un solo registro pese a la entrega fallida, el reintento y la repetición. Datos eliminados al terminar. Estado VC01: **PASS** (resultado inicial).

## Checks

`uv run python -m quality.check` sobre `b553a22` (con `.env` exportado): PASS format, lint, types (mypy strict), hygiene, migrations (upgrade/downgrade/upgrade + `alembic check`), tests (341 passed, Postgres real aislado), api (16 contratos sin diferencias).

## Supresiones

Sin supresiones nuevas.

## Umbral

AC PASS / AC aplicables = 3/3 = **100%**.

## Review Standards/Spec

Pendiente.
