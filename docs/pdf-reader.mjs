import { ColorSpace, Document, Matrix } from './vendor/mupdf/mupdf.js';

async function openPdf(file) {
  const doc = Document.openDocument(await file.arrayBuffer(), 'application/pdf');
  if (doc.needsPassword() || !doc.countPages()) {
    doc.destroy();
    throw new Error('Wybierz PDF bez hasła z co najmniej jedną stroną.');
  }
  return doc;
}

function png(page, requestedScale) {
  const [x0, y0, x1, y1] = page.getBounds();
  const scale = Math.min(requestedScale, Math.sqrt(12000000 / Math.max(1, (x1 - x0) * (y1 - y0))));
  const pixels = page.toPixmap(Matrix.scale(scale, scale), ColorSpace.DeviceRGB, false);
  try {
    return new Blob([pixels.asPNG()], {type: 'image/png'});
  } finally {
    pixels.destroy();
  }
}

export async function preview(file) {
  const doc = await openPdf(file);
  try {
    const page = doc.loadPage(0);
    try { return png(page, 1.5); }
    finally { page.destroy(); }
  } finally { doc.destroy(); }
}

async function startOcr() {
  const { default: tesseract } = await import('./vendor/tesseract/tesseract.esm.min.js');
  const url = path => new URL(path, import.meta.url).href;
  return new Promise((resolve, reject) => {
    tesseract.createWorker('pol+eng', tesseract.OEM.LSTM_ONLY, {
      workerPath: url('./vendor/tesseract/worker.min.js'), workerBlobURL: false,
      corePath: url('./vendor/tesseract/'), langPath: url('./tessdata/'),
      errorHandler: message => reject(new Error(String(message))),
    }).then(resolve, reject);
  });
}

export async function readPages(file, onProgress = () => {}) {
  const doc = await openPdf(file);
  const pages = [];
  let worker;
  try {
    const count = doc.countPages();
    for (let i = 0; i < count; i++) {
      onProgress(`Odczyt strony ${i + 1} z ${count}…`);
      const page = doc.loadPage(i);
      try {
        const layer = page.toStructuredText('preserve-images');
        let text, needsOcr;
        try {
          text = layer.asText().replace(/\n{2,}/g, '\n');
          const letters = (text.match(/\p{L}/gu) || []).length;
          needsOcr = letters < 18 || (text.match(/\uFFFD/g) || []).length > Math.max(2, letters / 20);
          if (!needsOcr && letters < 220) {
            const [x0, y0, x1, y1] = page.getBounds();
            needsOcr = JSON.parse(layer.asJSON()).blocks.some(b => b.type === 'image' &&
              b.bbox.w * b.bbox.h > 0.65 * (x1 - x0) * (y1 - y0));
          }
        } finally { layer.destroy(); }
        if (needsOcr) {
          onProgress(`Rozpoznawanie tekstu (OCR), strona ${i + 1} z ${count}…`);
          worker ??= await startOcr();
          const { data } = await worker.recognize(png(page, 300 / 72));
          if (data.text.trim()) text = data.text;
        }
        pages.push(text.normalize('NFC').replaceAll('\u00A0', ' ').trim());
      } finally { page.destroy(); }
    }
    return pages;
  } finally {
    doc.destroy();
    if (worker) await worker.terminate();
  }
}
