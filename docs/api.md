# API de KinderClose (ingeniería inversa)

KinderClose no publica una API documentada. Esta descripción se ha obtenido por ingeniería inversa de la app oficial **KinderClose Familiar** (paquete Android `com.kinderclose.familiar`, versión 3.3.10). La app está hecha con Ionic y Angular, y su código JavaScript incluye las llamadas, cabeceras y modelos de datos. Desde la versión 1.0.0, la integración usa esta API en lugar de analizar el HTML de la web.

Los nombres de los campos y los formatos salen del código de la app. Contra la API real solo se han comprobado las respuestas de error (credenciales incorrectas y peticiones sin token); las respuestas correctas no se han verificado todavía con una cuenta. Cualquier cambio de KinderClose en la app puede cambiar la API sin aviso. El cliente tolera variaciones razonables: números como texto, fechas en distintos formatos ISO y respuestas envueltas en `{"data": ...}`. Para comprobar la API con una cuenta real sin mostrar datos personales, usa `scripts/probe_api.py` (ver [mantenimiento](maintenance.md)).

## Conexión

- Base: `https://app.kinderclose.com/api/v3`, en JSON. La API responde a los errores con `{"error": {"message", "status_code"}}`.
- Límite de peticiones: `X-RateLimit-Limit: 30` (por minuto). Un 429 se trata como un error de conexión temporal.
- La API no usa cookies ni redirecciones. El cliente no sigue redirecciones y usa una sesión HTTP sin cookies.

## Autenticación

`POST /auth/login`

```json
{"email": "…", "password": "…", "provider": 1, "deviceName": "Home Assistant", "deviceType": 1, "appVersion": null}
```

- `provider`: 1 local (correo y contraseña), 2 Facebook, 3 Google, 4 Apple. La integración solo admite el valor 1.
- `deviceType`: 1 web, 2 iOS, 3 Android. La integración se identifica como web, igual que la versión web de la app.
- Respuesta correcta: `userId`, `userName`, `userLastName`, `userEmail`, `userImage`, `rol`, `reportErrors`, `centros`, `deviceId` y `token`.
- Credenciales incorrectas: `401 {"error": {"message": "Unauthorized.", "status_code": 401}}`.

Cada inicio de sesión registra un dispositivo en la cuenta. Las peticiones posteriores envían la cabecera `token: <token>` y el parámetro `device_id=<deviceId>`. Un 401 indica que el token ya no vale: la app cierra la sesión, y la integración inicia sesión de nuevo una sola vez. La integración guarda el token en la entrada de configuración, así que no registra un dispositivo nuevo en cada reinicio. `POST /auth/logout` (autenticado) retira el dispositivo; la integración lo llama al eliminar la última entrada que usa ese token.

## Endpoints que usa la integración

| Petición | Uso |
| --- | --- |
| `GET /familiar/alumno` | Lista de alumnos de la cuenta: `id`, `nombre`, `apellidos`, `avatar`, `enabled`, `fechaNacimiento`… |
| `GET /familiar/alumno/{id}/ficha/null` | Ficha de hoy (lo que pide la app al abrir un alumno). |
| `GET /familiar/alumno/{id}/ficha/null?fecha=AAAA-MM-DD` | Ficha de un día concreto. |
| `POST /auth/login`, `POST /auth/logout` | Sesión del dispositivo. |

Si un día no tiene ficha, la app recibe un error y muestra «Ficha sin información». El cliente trata como «sin ficha» un 404, un cuerpo vacío y una ficha con `id` nulo.

La app también usa otros endpoints que la integración no consulta: `/familiar/alumno/{id}/menu/null`, `/familiar/alumno/{id}/mensaje`, `/familiar/alumno/{id}/stats`, `/familiar/evento`, `/familiar/autorizacion`, `/familiar/infocentro` y `/user`.

## Ficha

| Campo | Formato | Normalización en la integración |
| --- | --- | --- |
| `id`, `alumno_id` | Entero | `url`: enlace a la ficha en la web. |
| `fecha` | Fecha ISO. Laravel puede serializarla en UTC (`2026-11-24T23:00:00.000000Z` para el 25 en Madrid). | Se convierte a la zona horaria de Home Assistant antes de tomar el día. |
| `ausente`, `ausencia_justificada` | 0/1 o booleano | `presencia.ausente`, `presencia.ausencia_justificada` (booleanos). |
| `hora_entrada`, `hora_salida`, `hora_entrada_tarde`, `hora_salida_tarde` | Fecha y hora, o `null` | `HH:MM` en la zona horaria de Home Assistant. |
| `comida_desayuno`, `comida_primero`, `comida_segundo`, `comida_postre`, `comida_merienda` | 0 sin dato, 1 Nada, 2 Poco, 3 Bastante, 4 Todo | Texto de la app (`Todo`, `Bastante`, `Poco`, `Nada`) o `null`. |
| `lista_dormir[]` | `hora_desde`, `hora_hasta` | `sueno[]` con `desde` y `hasta`; `sueno_minutos` suma las siestas completas. |
| `lista_deposicion[]` | `tipo` (1 Deposición, 2 Pis), `hora_desde`, `info` | `deposiciones[]` con `tipo`, `hora` e `info`. |
| `lista_biberon[]` | `hora_desde`, `cantidad` (ml) | `biberones[]` con `hora` y `cantidad`. |
| `recordatorios[]` | 1 Toallitas, 2 Pañales, 3 Agua, 4 Muda, u objeto `{id, label}` para los personalizados | `recordatorios[]` con el texto. |
| `control_esfinter` | -1 sin dato, 0 No, 1 Sí | `control_esfinter`: `No`, `Sí` o `null`. |
| `editable` | Booleano | No se usa. |
