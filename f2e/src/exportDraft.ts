import { draftPdfDefinition } from './draftPdf'
import { createDocx } from './draftDocx'
import { fixture } from './data/demo'

export interface DraftMeta { caseLabel: string; appellant: string; agency: string; caseType: string }
export type DraftParts = typeof fixture.draft
export const FIXTURE_META: DraftMeta = { caseLabel: '113-16', appellant: '王小明', agency: '新北市政府警察局新店分局', caseType: '違反洗錢防制法事件' }

export async function exportDraft(format: 'pdf' | 'docx', draft: DraftParts = fixture.draft, meta: DraftMeta = FIXTURE_META) {
  let blob: Blob
  if (format === 'pdf') {
    const { default: pdfMake } = await import('pdfmake/build/pdfmake')
    const fontUrl = new URL(`${import.meta.env.BASE_URL}fonts/NotoSerifTC-Regular.otf`, window.location.origin).href
    pdfMake.addFonts({ NotoSerifTC: { normal: fontUrl, bold: fontUrl, italics: fontUrl, bolditalics: fontUrl } })
    blob = await pdfMake.createPdf(draftPdfDefinition(draft, meta)).getBlob()
  } else {
    blob = await createDocx(draft, meta)
  }
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${meta.caseLabel}_訴願決定書_草稿.${format}`
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
