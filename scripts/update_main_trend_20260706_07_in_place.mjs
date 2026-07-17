import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-已更新.xlsx");
const outputDir = "output/main_trend_update_20260706_07";

const styles = {
  plusLight: { color: "F4B183" },
  plusDark: { color: "FF0000" },
  minusLight: { color: "92D050" },
  minusDark: { color: "00B050" },
};

const dateUpdates = [
  {
    date: "2026-07-06",
    serial: 46209,
    updates: new Map([
      ["红枣", ["家人-", "内资-"]],
      ["生猪", ["家人-", "内资-"]],
      ["银", ["家人-"]],
      ["玻璃", ["家人-", "内资-", "外资-"]],
      ["氧化铝", ["家人-", "内资-"]],
      ["鸡蛋", ["家人+", "内资+"]],
      ["烧碱", ["家人+"]],
      ["燃油", ["家人+", "内资+"]],
      ["纸浆", ["内资-"]],
      ["锡", ["内资+", "外资+"]],
      ["菜油", ["内资+", "外资+"]],
      ["豆油", ["内资+", "外资+"]],
      ["豆粕", ["内资+", "外资+"]],
      ["PP", ["内资+"]],
      ["硅铁", ["外资+"]],
      ["棕榈油", ["外资+"]],
      ["菜粕", ["外资+"]],
      ["螺纹钢", ["外资+"]],
      ["PVC", ["外资-"]],
    ]),
  },
  {
    date: "2026-07-07",
    serial: 46210,
    updates: new Map([
      ["红枣", ["家人-", "内资-"]],
      ["玻璃", ["家人-", "内资-", "外资-"]],
      ["纯碱", ["家人-", "内资-", "外资-"]],
      ["氧化铝", ["家人-", "内资-"]],
      ["烧碱", ["家人-", "内资-"]],
      ["豆油", ["内资+", "外资+"]],
      ["菜油", ["内资+", "外资+"]],
      ["锌", ["内资+", "外资+"]],
      ["甲醇", ["内资+"]],
      ["PP", ["内资+"]],
      ["天然橡胶", ["内资+"]],
      ["苯乙烯", ["内资+"]],
      ["豆粕", ["外资+"]],
      ["菜粕", ["外资+"]],
      ["20号胶", ["外资+"]],
      ["棕榈油", ["外资+"]],
      ["热卷", ["外资-"]],
    ]),
  },
];

function chooseStyle(tags) {
  const hasInnerPlus = tags.includes("内资+");
  const hasOuterPlus = tags.includes("外资+");
  const hasInnerMinus = tags.includes("内资-");
  const hasOuterMinus = tags.includes("外资-");

  if (hasInnerPlus && hasOuterPlus) return styles.plusDark;
  if (hasInnerMinus && hasOuterMinus) return styles.minusDark;
  if (hasInnerPlus || hasOuterPlus) return styles.plusLight;
  if (hasInnerMinus || hasOuterMinus) return styles.minusLight;
  if (tags.some((tag) => tag.endsWith("+"))) return styles.plusLight;
  if (tags.some((tag) => tag.endsWith("-"))) return styles.minusLight;
  return null;
}

function directionFromTags(tags) {
  if (tags.includes("内资+") && tags.includes("外资+")) return "+";
  if (tags.includes("内资-") && tags.includes("外资-")) return "-";
  return null;
}

function excelSerialToDate(serial) {
  const epoch = Date.UTC(1899, 11, 30);
  const date = new Date(epoch + Number(serial) * 86400000);
  return date.toISOString().slice(0, 10);
}

function normalizeTags(value) {
  return String(value ?? "")
    .split(/\r?\n/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function columnAddress(sheet, col) {
  return sheet.getRangeByIndexes(0, col, 1, 1).address.replace(/\d+$/, "");
}

function repeatedConsecutiveItems(items, last3DateCols) {
  const indexByDate = new Map(last3DateCols.map((col, index) => [col.date, index]));
  const byVariety = new Map();
  for (const item of items) {
    if (!byVariety.has(item.variety)) byVariety.set(item.variety, []);
    byVariety.get(item.variety).push({ ...item, index: indexByDate.get(item.date) });
  }

  const repeated = [];
  for (const [variety, rows] of byVariety.entries()) {
    const sorted = rows
      .filter((row) => row.index !== undefined)
      .sort((a, b) => a.index - b.index);
    let best = [];
    let current = [];
    for (const row of sorted) {
      const previous = current[current.length - 1];
      if (previous && row.index === previous.index + 1 && row.direction === previous.direction) {
        current.push(row);
      } else {
        if (current.length > best.length) best = current;
        current = [row];
      }
    }
    if (current.length > best.length) best = current;
    if (best.length >= 2) repeated.push({ variety, direction: best[0].direction, count: best.length, rows: best });
  }

  return repeated.sort((a, b) => b.count - a.count || a.variety.localeCompare(b.variety, "zh-Hans-CN"));
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;
const header = values[1];

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const allWritten = [];
const allMissing = [];
const targetColumns = [];
for (const { date, serial, updates } of dateUpdates) {
  const targetCol = header.findIndex((value) => Number(value) === serial);
  if (targetCol < 0) throw new Error(`Could not find ${date} column with serial ${serial}.`);
  const targetColumn = columnAddress(sheet, targetCol);
  targetColumns.push({ date, serial, column: targetColumn, col: targetCol });

  const dataRowStart = 2;
  const dataRowCount = values.length - dataRowStart;
  const targetDataRange = sheet.getRangeByIndexes(dataRowStart, targetCol, dataRowCount, 1);
  const formatSourceCol = targetCol + 1 < header.length ? targetCol + 1 : targetCol - 1;
  if (formatSourceCol >= 0) {
    targetDataRange.copyFrom(sheet.getRangeByIndexes(dataRowStart, formatSourceCol, dataRowCount, 1), "formats");
  }
  targetDataRange.values = Array.from({ length: dataRowCount }, () => [null]);

  for (const [variety, tags] of updates.entries()) {
    const row = rowByVariety.get(variety);
    if (row === undefined) {
      allMissing.push({ date, variety, reason: "missing-row" });
      continue;
    }

    const target = sheet.getRangeByIndexes(row, targetCol, 1, 1);
    const style = chooseStyle(tags);
    target.values = [[tags.join("\n")]];
    target.format.wrapText = tags.length > 1;
    if (style) target.format.fill.color = style.color;

    allWritten.push({
      date,
      variety,
      row1: row + 1,
      col1: targetCol + 1,
      address: `${targetColumn}${row + 1}`,
      value: tags.join("\n"),
      color: style?.color ?? "",
      status: "updated",
    });
  }
}

const finalSerial = dateUpdates.at(-1).serial;
const availableDateCols = [];
for (let c = 0; c < header.length; c += 1) {
  const serial = Number(header[c]);
  if (Number.isFinite(serial) && serial <= finalSerial) {
    const hasData = [...rowByVariety.values()].some((row) => {
      const value = sheet.getRangeByIndexes(row, c, 1, 1).values?.[0]?.[0];
      return String(value ?? "").trim() !== "";
    });
    if (hasData) {
      availableDateCols.push({ serial, col: c, date: excelSerialToDate(serial), column: columnAddress(sheet, c) });
    }
  }
}
const last3DateCols = availableDateCols.slice(-3);

const innerOuterSame = [];
const tripleResonance = [];
for (const dateCol of last3DateCols) {
  for (const [variety, row] of rowByVariety.entries()) {
    const tags = normalizeTags(sheet.getRangeByIndexes(row, dateCol.col, 1, 1).values?.[0]?.[0]);
    const direction = directionFromTags(tags);
    if (!direction) continue;

    const item = {
      date: dateCol.date,
      serial: dateCol.serial,
      column: dateCol.column,
      variety,
      direction,
      tags,
    };
    innerOuterSame.push(item);
    if (tags.includes(`家人${direction}`)) tripleResonance.push(item);
  }
}

const resonanceSummary = {
  generatedFor: dateUpdates.at(-1).date,
  last3Dates: last3DateCols.map(({ date, serial, column }) => ({ date, serial, column })),
  innerOuterSame,
  tripleResonance,
  repeatedInnerOuterSame: repeatedConsecutiveItems(innerOuterSame, last3DateCols),
  repeatedTripleResonance: repeatedConsecutiveItems(tripleResonance, last3DateCols),
};

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(
  `${outputDir}/written_cells.json`,
  JSON.stringify({ workbookPath, targetColumns, written: allWritten, missing: allMissing }, null, 2),
  "utf8",
);
await fs.writeFile(`${outputDir}/strong_resonance_last3days.json`, JSON.stringify(resonanceSummary, null, 2), "utf8");

const previewStart = last3DateCols[0].column;
const previewEnd = last3DateCols.at(-1).column;
const preview = await workbook.render({ sheetName: sheet.name, range: `${previewStart}1:${previewEnd}57`, scale: 2, format: "png" });
await fs.writeFile(`${outputDir}/fj_fm_columns_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(workbookPath);

console.log(JSON.stringify({
  workbookPath,
  outputDir,
  targetColumns: targetColumns.map(({ date, serial, column }) => ({ date, serial, column })),
  updated: allWritten.length,
  missing: allMissing,
  last3Dates: resonanceSummary.last3Dates,
  innerOuterSameCount: innerOuterSame.length,
  tripleResonanceCount: tripleResonance.length,
  repeatedInnerOuterSame: resonanceSummary.repeatedInnerOuterSame.map(({ variety, direction, count }) => ({ variety, direction, count })),
  repeatedTripleResonance: resonanceSummary.repeatedTripleResonance.map(({ variety, direction, count }) => ({ variety, direction, count })),
}, null, 2));
