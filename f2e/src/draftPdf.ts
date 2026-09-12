import type { Content, TDocumentDefinitions } from 'pdfmake/interfaces'
import { fixture } from './data/demo'
import type { DraftMeta, DraftParts } from './exportDraft'

export function draftPdfDefinition(draft: DraftParts = fixture.draft, meta: DraftMeta = { caseLabel: '113-16', appellant: '王小明', agency: '新北市政府警察局新店分局', caseType: '違反洗錢防制法事件' }): TDocumentDefinitions {
  const headingColor = '#344157'
  return {
    pageSize: 'A4', pageMargins: [48, 42, 48, 44],
    defaultStyle: { font: 'NotoSerifTC', fontSize: 11, lineHeight: 1.65, color: '#576174' },
    info: { title: `${meta.caseLabel} 訴願決定書草稿`, author: '新北市政府法制局' },
    content: [
      { columns: [
        { text: '新北市政府', color: headingColor, fontSize: 11, characterSpacing: 2 },
        { width: 46, table: { body: [[{ text: '草 稿', fontSize: 9, color: '#af9569', alignment: 'center', margin: [4, 1, 4, 1] }]] }, layout: { hLineColor: () => '#ccba9d', vLineColor: () => '#ccba9d', hLineWidth: () => 0.6, vLineWidth: () => 0.6 } },
      ], margin: [0, 0, 0, 12] },
      { text: '訴願決定書', alignment: 'center', fontSize: 25, characterSpacing: 6, color: headingColor, margin: [0, 0, 0, 4] },
      { text: `案號：${meta.caseLabel}`, alignment: 'center', fontSize: 9, color: '#8991a0', margin: [0, 0, 0, 20] },
      { table: { widths: [74, '*'], body: [
        ['訴願人', meta.appellant], ['原處分機關', meta.agency], ['案由', meta.caseType],
      ].map(([label, value]) => [{ text: label!, color: '#7d8795' }, { text: value!, color: headingColor }]) }, fontSize: 10,
        layout: { hLineWidth: (i, node) => i === 0 || i === node.table.body.length ? 0.5 : 0, vLineWidth: () => 0, hLineColor: () => '#e5e8ed', paddingLeft: () => 0, paddingRight: () => 10, paddingTop: () => 6, paddingBottom: () => 6 }, margin: [0, 0, 0, 18] },
      { text: '訴願人因違反洗錢防制法事件，不服原處分機關所為之書面告誡，提起訴願，本府決定如下：', color: headingColor },
      ...draft.flatMap((part): Content[] => [
        { columns: [
          { width: 8, canvas: [{ type: 'rect', x: 0, y: 6, w: 2.5, h: 12, color: '#577981' }] },
          { text: part.title, fontSize: 14, characterSpacing: 2, color: headingColor },
          { text: part.citations.length ? `${part.citations.length} 筆引用` : part.title === '教示' ? '待人工補正' : '依案件摘要', alignment: 'right', fontSize: 8, color: '#7d9493', margin: [0, 5, 0, 0] },
        ], margin: [0, 18, 0, 6], headlineLevel: 1 },
        { text: part.text, alignment: 'justify' },
      ]),
      { canvas: [{ type: 'line', x1: 0, y1: 0, x2: 499, y2: 0, lineWidth: 0.5, lineColor: '#e8ebef' }], margin: [0, 22, 0, 10] },
      { text: '草稿內容須由承辦人核對事實、引用依據及救濟教示。', alignment: 'center', fontSize: 8, color: '#a2a8b0' },
    ],
    pageBreakBefore: (current, container) => current.headlineLevel === 1 && ((current.startPosition?.verticalRatio ?? 0) > 0.86 || container.getFollowingNodesOnPage().length === 0),
    footer: (page, total) => ({ text: `${page} / ${total}`, alignment: 'center', fontSize: 8, color: '#a2a8b0' }),
  }
}
