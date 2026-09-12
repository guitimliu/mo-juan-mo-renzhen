import { draft } from './data/demo'

export async function createDocx() {
  const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, BorderStyle, Footer, PageNumber, TabStopType } = await import('docx')
  const body = (text: string) => new Paragraph({
    alignment: AlignmentType.JUSTIFIED, widowControl: true,
    children: text.split('\n').map((line, index) => new TextRun({ text: line, break: index ? 1 : 0 })),
  })
  const document = new Document({
    title: '113-16 訴願決定書草稿', creator: '新北市政府法制局',
    styles: {
      default: { document: { run: { font: '新細明體', size: 24, color: '576174' }, paragraph: { spacing: { after: 160, line: 400 } } } },
      paragraphStyles: [
        { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: '新細明體', size: 48, color: '344157' }, paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true } },
        { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', run: { font: '新細明體', size: 30, color: '344157', bold: true }, paragraph: { spacing: { before: 300, after: 120 }, keepNext: true } },
      ],
    },
    sections: [{
      properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 900, bottom: 900, left: 960, right: 960 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT, ' / ', PageNumber.TOTAL_PAGES], size: 18, color: 'A2A8B0' })] })] }) },
      children: [
        new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: 9986 }], children: [new TextRun({ text: '新北市政府', color: '344157' }), new TextRun({ text: '\t草 稿', color: 'AF9569', size: 20 })] }),
        new Paragraph({ text: '訴願決定書', heading: HeadingLevel.TITLE }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 320 }, children: [new TextRun({ text: '案號：113-16', size: 20, color: '8991A0' })], keepNext: true }),
        ...[['訴願人', '王小明'], ['原處分機關', '新北市政府警察局新店分局'], ['案由', '違反洗錢防制法事件']].map(([label, value], i) => new Paragraph({
          tabStops: [{ type: TabStopType.LEFT, position: 1700 }], keepNext: true,
          spacing: { before: i === 0 ? 160 : 0, after: i === 2 ? 280 : 100 },
          border: i === 0 ? { top: { color: 'E5E8ED', style: BorderStyle.SINGLE, size: 4, space: 10 } } : i === 2 ? { bottom: { color: 'E5E8ED', style: BorderStyle.SINGLE, size: 4, space: 10 } } : undefined,
          children: [new TextRun({ text: label!, color: '7D8795', size: 22 }), new TextRun({ text: '\t' + value!, color: '344157', size: 22 })],
        })),
        body('訴願人因違反洗錢防制法事件，不服原處分機關所為之書面告誡，提起訴願，本府決定如下：'),
        ...draft.flatMap(part => [
          new Paragraph({ heading: HeadingLevel.HEADING_1, border: { left: { color: '577981', style: BorderStyle.SINGLE, size: 18, space: 8 } }, tabStops: [{ type: TabStopType.RIGHT, position: 9986 }], children: [
            new TextRun(part.title),
            new TextRun({ text: '\t' + (part.citations.length ? `${part.citations.length} 筆引用` : part.title === '教示' ? '待人工補正' : '依案件摘要'), bold: false, size: 18, color: '7D9493' }),
          ] }),
          body(part.text),
        ]),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 320 }, border: { top: { color: 'E8EBEF', style: BorderStyle.SINGLE, size: 4, space: 10 } }, children: [new TextRun({ text: '草稿內容須由承辦人核對事實、引用依據及救濟教示。', size: 18, color: 'A2A8B0' })] }),
      ],
    }],
  })
  return Packer.toBlob(document)
}
