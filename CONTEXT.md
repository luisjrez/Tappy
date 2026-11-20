# Tappy

Herramienta de cobros para micronegocios mexicanos. Coordina solicitudes CoDi y permite consultar los pagos confirmados que recibe el comercio en su cuenta bancaria.

## Lenguaje

**Comercio / Merchant**:
Negocio que solicita un cobro y tiene una cuenta receptora autorizada.
_Evitar_: cliente, cuenta.

**Operador / Operator**:
Persona del comercio que utiliza Tappy para crear y consultar cobros.
_Evitar_: pagador, comercio cuando se habla de una persona.

**Pagador / Payer**:
Persona que revisa y autoriza el pago desde su institución bancaria compatible.
_Evitar_: usuario de Tappy, cliente registrado.

**Cuenta receptora / ReceivingAccount**:
Cuenta bancaria autorizada para recibir los cobros de un comercio.
_Evitar_: saldo Tappy, billetera.

**Cobro / Sale**:
Obligación comercial de recibir un importe determinado por una venta. Puede tener varios intentos, sin que cada reintento represente otra venta.
_Evitar_: Payment, transacción, solicitud como sinónimos.

**Intento de cobro / PaymentAttempt**:
Solicitud individual por QR, celular o enlace asociada a un cobro. Su creación o envío no acredita que se haya recibido dinero.
_Evitar_: pago, transferencia confirmada.

**Transferencia confirmada / Transaction**:
Movimiento bancario cuya evidencia de recepción ha sido validada y vinculada a una cuenta receptora. Dos movimientos distintos son dos transferencias, aunque correspondan al mismo cobro.
_Evitar_: intento, autorización inferida.

**Evento del proveedor / WebhookEvent**:
Notificación enviada por pey sobre una operación o una cuenta. Puede repetirse y requiere validación antes de modificar el registro del cobro.
_Evitar_: pago confirmado como sinónimo de cualquier notificación.

**Conciliación / Reconciliation**:
Comprobación y asociación de evidencia del proveedor con los cobros y transferencias registrados por Tappy.
_Evitar_: asumir pago, marcar manualmente como pagado.

**Importe recibido / ReceivedAmount**:
Suma de transferencias confirmadas asociadas al comercio para un periodo explícito.
_Evitar_: saldo bancario, utilidad, solicitudes generadas.

**Incidencia de cobro / PaymentException**:
Situación que necesita revisión porque el importe, la referencia, la cuenta o la cantidad de transferencias no coincide con el cobro esperado.
_Evitar_: pago fallido para todo caso incierto.

**Modo demostración / DemoMode**:
Experiencia con operaciones sintéticas identificadas como simuladas, separada de las operaciones bancarias.
_Evitar_: sandbox de pey, pago real.
