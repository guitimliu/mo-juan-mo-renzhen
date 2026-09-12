import { draftPdfDefinition } from './draftPdf'
import { createDocx } from './draftDocx'

export async function exportDraft(format: 'pdf' | 'docx') {
  let blob: Blob
  if (format === 'pdf') {
    const { default: pdfMake } = await import('pdfmake/build/pdfmake')
    const fontUrl = new URL(`${import.meta.env.BASE_URL}fonts/NotoSerifTC-Regular.otf`, window.location.origin).href
    pdfMake.addFonts({ NotoSerifTC: { normal: fontUrl, bold: fontUrl, italics: fontUrl, bolditalics: fontUrl } })
    blob = await pdfMake.createPdf(draftPdfDefinition()).getBlob()
  } else {
    blob = await createDocx()
  }
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `113-16_訴願決定書_草稿.${format}`
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
