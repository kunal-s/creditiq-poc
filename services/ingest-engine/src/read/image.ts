// Page-image measurements for the quality grade: ink (blank pages),
// sharpness (blur), background spread (shadow). Computed on a grey copy
// scaled to a fixed width so the numbers are comparable between scans.


type CanvasMod = typeof import('@napi-rs/canvas')
let canvasMod: Promise<CanvasMod> | null = null
export const canvasImport = (): Promise<CanvasMod> => (canvasMod ??= import('@napi-rs/canvas'))

const WORK_WIDTH = 1000

export interface LoadedImage { png: Uint8Array; width: number; height: number }

/** Decode an image file (PNG, JPEG, WebP, GIF, BMP) and re-encode as PNG for OCR. */
export async function loadImageFile(buf: Uint8Array): Promise<LoadedImage> {
  const { createCanvas, loadImage } = await canvasImport()
  const img = await loadImage(Buffer.from(buf))
  const c = createCanvas(img.width, img.height)
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, img.width, img.height)
  ctx.drawImage(img, 0, 0)
  return { png: new Uint8Array(await c.encode('png')), width: img.width, height: img.height }
}

export async function measure(png: Uint8Array): Promise<{ ink: number; sharpness: number; shadow: number; width: number; height: number }> {
  const { createCanvas, loadImage } = await canvasImport()
  const img = await loadImage(Buffer.from(png))
  const w = Math.min(WORK_WIDTH, img.width)
  const h = Math.max(1, Math.round((img.height * w) / img.width))
  const c = createCanvas(w, h)
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, w, h)
  ctx.drawImage(img, 0, 0, w, h)
  const { data } = ctx.getImageData(0, 0, w, h)
  const grey = new Float32Array(w * h)
  let dark = 0
  for (let i = 0, j = 0; j < grey.length; i += 4, j++) {
    const g = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
    grey[j] = g
    if (g < 128) dark++
  }
  const ink = dark / grey.length
  // Sharpness: variance of the 4-neighbour Laplacian, over pixels near ink
  // only (plain paper would dilute it).
  let sum = 0
  let sumSq = 0
  let n = 0
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const k = y * w + x
      const lap = grey[k - 1] + grey[k + 1] + grey[k - w] + grey[k + w] - 4 * grey[k]
      if (grey[k] < 200 || Math.abs(lap) > 8) { sum += lap; sumSq += lap * lap; n++ }
    }
  }
  const sharpness = n ? Math.round(sumSq / n - (sum / n) ** 2) : 0
  // Shadow: the bright (paper) level in each cell of an 4x4 grid; the spread
  // between the brightest and the darkest paper level.
  const levels: number[] = []
  const gw = Math.floor(w / 4)
  const gh = Math.floor(h / 4)
  for (let gy = 0; gy < 4; gy++) {
    for (let gx = 0; gx < 4; gx++) {
      const hist = new Uint32Array(256)
      let cnt = 0
      for (let y = gy * gh; y < (gy + 1) * gh; y += 2) {
        for (let x = gx * gw; x < (gx + 1) * gw; x += 2) { hist[Math.min(255, Math.max(0, Math.round(grey[y * w + x])))]++; cnt++ }
      }
      // 90th percentile brightness = the paper level.
      let acc = 0
      let level = 255
      for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc >= cnt * 0.9) { level = v; break } }
      levels.push(level)
    }
  }
  const shadow = levels.length ? Math.max(...levels) - Math.min(...levels) : 0
  return { ink: Math.round(ink * 10000) / 10000, sharpness, shadow, width: img.width, height: img.height }
}
