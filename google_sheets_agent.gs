const AGENT_URL = 'https://REEMPLAZA-ESTA-URL/process';
const AGENT_TOKEN = 'REEMPLAZA-ESTE-TOKEN';

function instalarAgente() {
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'alEditarHoja') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger('alEditarHoja')
    .forSpreadsheet(SpreadsheetApp.getActive())
    .onEdit()
    .create();
}

function alEditarHoja(evento) {
  const hoja = evento.range.getSheet();
  const fila = evento.range.getRow();
  if (fila === 1) return;

  const encabezados = hoja.getRange(1, 1, 1, hoja.getLastColumn())
    .getValues()[0]
    .map(normalizar);
  const enlaceCol = buscarColumna(encabezados, ['doi / enlace']);
  const docOrigenCol = buscarColumna(encabezados, ['link del doc']);
  const docCol = buscarColumna(encabezados, ['enlace con articulo traducido']);
  const originalCol = buscarColumna(encabezados, ['fragmento tal y como esta']);
  const traduccionCol = buscarColumna(encabezados, [
    'fragemento traducido',
    'fragmento traducido',
  ]);
  if (!enlaceCol || !docOrigenCol || !docCol || !originalCol || !traduccionCol) {
    throw new Error('No se encontraron todos los encabezados requeridos.');
  }

  const editCol = evento.range.getColumn();
  if (editCol !== enlaceCol && editCol !== docOrigenCol && editCol !== originalCol) return;

  const valores = hoja.getRange(fila, 1, 1, hoja.getLastColumn()).getValues()[0];
  const enlace = String(valores[enlaceCol - 1] || '').trim();
  const linkDoc = String(valores[docOrigenCol - 1] || '').trim();
  const fragmento = String(valores[originalCol - 1] || '').trim();
  const docExistente = String(valores[docCol - 1] || '').trim();
  const fragmentoTraducido = String(valores[traduccionCol - 1] || '').trim();
  if (!enlace && !linkDoc && !fragmento) return;

  let textoDoc = null;
  let pdfBase64 = null;
  if (linkDoc && !docExistente && linkDoc.indexOf('docs.google.com/document') !== -1) {
    try {
      textoDoc = DocumentApp.openByUrl(linkDoc).getBody().getText().trim();
    } catch (error) {
      hoja.getRange(fila, editCol).setNote('No se pudo leer el Google Doc: ' + error.message);
      return;
    }
  }
  if (linkDoc && !docExistente && esEnlaceDrive(linkDoc)) {
    try {
      const archivoId = extraerIdDrive(linkDoc);
      pdfBase64 = Utilities.base64Encode(DriveApp.getFileById(archivoId).getBlob().getBytes());
    } catch (error) {
      hoja.getRange(fila, editCol).setNote('No se pudo leer el PDF de Drive: ' + error.message);
      return;
    }
  }

  const payload = {
    source_url: (linkDoc && !textoDoc && !pdfBase64) ? linkDoc : (enlace && !docExistente ? enlace : null),
    source_text: textoDoc,
    pdf_base64: pdfBase64,
    fragment: fragmento && !fragmentoTraducido ? fragmento : null,
  };
  if (!payload.source_url && !payload.source_text && !payload.pdf_base64 && !payload.fragment) return;
  const respuesta = UrlFetchApp.fetch(AGENT_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + AGENT_TOKEN,
      'ngrok-skip-browser-warning': 'true',
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  const codigo = respuesta.getResponseCode();
  const cuerpo = respuesta.getContentText();
  let resultado;
  try {
    resultado = JSON.parse(cuerpo);
  } catch (error) {
    hoja.getRange(fila, editCol).setNote(
      'El agente no devolvió JSON (' + codigo + '). '
      + 'Verifica que Uvicorn y ngrok estén activos y que AGENT_URL sea actual. '
      + cuerpo.substring(0, 180)
    );
    return;
  }
  if (codigo < 200 || codigo >= 300) {
    hoja.getRange(fila, editCol).setNote('Agente: ' + (resultado.detail || 'error desconocido'));
    return;
  }

  if (resultado.translated_article && !docExistente) {
    const titulo = String(valores[1] || 'Artículo traducido');
    const documento = DocumentApp.create(titulo);
    documento.getBody().setText(resultado.translated_article);
    documento.saveAndClose();
    hoja.getRange(fila, docCol).setValue(documento.getUrl());
  }
  if (resultado.translated_fragment && !fragmentoTraducido) {
    hoja.getRange(fila, traduccionCol).setValue(resultado.translated_fragment);
  }
}

function normalizar(valor) {
  return String(valor || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

function buscarColumna(encabezados, nombres) {
  for (const nombre of nombres) {
    const indice = encabezados.indexOf(nombre);
    if (indice >= 0) return indice + 1;
  }
  return null;
}

function extraerIdDrive(url) {
  const coincidencia = url.match(/\/d\/([a-zA-Z0-9_-]+)/) || url.match(/[?&]id=([a-zA-Z0-9_-]+)/);
  if (!coincidencia) throw new Error('El enlace no contiene un ID válido de Drive.');
  return coincidencia[1];
}

function esEnlaceDrive(url) {
  return url.indexOf('drive.google.com') !== -1 ||
    url.indexOf('docs.google.com/file') !== -1;
}