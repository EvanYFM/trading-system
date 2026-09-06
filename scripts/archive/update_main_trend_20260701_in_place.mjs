import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-6.16-已更新.xlsx");
const outputDir = "output/main_trend_update_20260701";

const targetSerial = 46204; // 2026-07-01
const targetDate = "2026-07-01";

const styles = {
  plusLight: { color: "F4B183" },
  plusDark: { color: "FF0000" },
  minusLight: { color: "92D050" },
  minusDark: { color: "00B050" },
};

const updates = new Map([
  ["银", ["家人-"]],
  ["玻璃", ["家人-", "内资-", "外资-"]],
  ["烧碱", ["家人-", "内资-"]],
  ["红枣", ["家人-", "内资-"]],
  ["燃油", ["家人-", "内资-"]],
  ["螺纹钢", ["内资-", "外资-"]],
  ["铝", ["内资-", "外资-"]],
  ["铁矿石", ["内资-", "外资-"]],
  ["焦煤", ["内资-"]],
  ["镍", ["内资-", "外资-"]],
  ["甲醇", ["内资-"]],
  ["鸡蛋", ["内资-"]],
  ["白糖", ["内资+", "外资+"]],
  ["纸浆", ["内资+", "外资+"]],
  ["花生", ["内资+", "外资+"]],
  ["碳酸锂", ["内资+", "外资+"]],
  ["PVC", ["外资-"]],
  ["塑料", ["外资-"]],
  ["豆一", ["外资-"]],
  ["热卷", ["外资-"]],
  ["乙二醇", ["外资+"]],
]);

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

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;
const header = values[1];
const targetCol = header.findIndex((value) => Number(value) === targetSerial);
if (targetCol < 0) throw new Error(`Could not find ${targetDate} column.`);

const targetAddress = sheet.getRangeByIndexes(0, targetCol, 1, 1).address.replace(/\d+$/, "");

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const dataRowStart = 2;
const dataRowCount = values.length - dataRowStart;
const targetDataRange = sheet.getRangeByIndexes(dataRowStart, targetCol, dataRowCount, 1);
const clearMatrix = Array.from({ length: dataRowCount }, () => [null]);

const formatSourceCol = targetCol + 1 < header.length ? targetCol + 1 : targetCol - 1;
if (formatSourceCol >= 0) {
  targetDataRange.copyFrom(sheet.getRangeByIndexes(dataRowStart, formatSourceCol, dataRowCount, 1), "formats");
}
targetDataRange.values = clearMatrix;

const written = [];
const missing = [];
for (const [variety, tags] of updates.entries()) {
  const row = rowByVariety.get(variety);
  if (row === undefined) {
    missing.push({ date: targetDate, variety, reason: "missing-row" });
    continue;
  }

  const target = sheet.getRangeByIndexes(row, targetCol, 1, 1);
  const style = chooseStyle(tags);
  target.values = [[tags.join("\n")]];
  target.format.wrapText = tags.length > 1;
  if (style) target.format.fill.color = style.color;

  written.push({
    date: targetDate,
    variety,
    row1: row + 1,
    col1: targetCol + 1,
    address: `${targetAddress}${row + 1}`,
    value: tags.join("\n"),
    color: style?.color ?? "",
    status: "updated",
  });
}

const availableDateCols = [];
for (let c = 0; c < header.length; c += 1) {
  const serial = Number(header[c]);
  if (Number.isFinite(serial) && serial <= targetSerial) {
    availableDateCols.push({ serial, col: c, date: excelSerialToDate(serial) });
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
      column: sheet.getRangeByIndexes(0, dateCol.col, 1, 1).address.replace(/\d+$/, ""),
      variety,
      direction,
      tags,
    };
    innerOuterSame.push(item);

    if (tags.includes(`家人${direction}`)) {
      tripleResonance.push(item);
    }
  }
}

function repeatedItems(items) {
  const byVariety = new Map();
  for (const item of items) {
    if (!byVariety.has(item.variety)) byVariety.set(item.variety, []);
    byVariety.get(item.variety).push(item);
  }
  return [...byVariety.entries()]
    .map(([variety, rows]) => ({ variety, count: rows.length, rows }))
    .filter((item) => item.count >= 2)
    .sort((a, b) => b.count - a.count || a.variety.localeCompare(b.variety, "zh-Hans-CN"));
}

const resonanceSummary = {
  generatedFor: targetDate,
  last3Dates: last3DateCols.map(({ date, serial, col }) => ({
    date,
    serial,
    column: sheet.getRangeByIndexes(0, col, 1, 1).address.replace(/\d+$/, ""),
  })),
  innerOuterSame,
  tripleResonance,
  repeatedInnerOuterSame: repeatedItems(innerOuterSame),
  repeatedTripleResonance: repeatedItems(tripleResonance),
};

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(
  `${outputDir}/written_cells.json`,
  JSON.stringify({ workbookPath, targetDate, targetSerial, targetColumn: targetAddress, written, missing }, null, 2),
  "utf8",
);
await fs.writeFile(`${outputDir}/strong_resonance_last3days.json`, JSON.stringify(resonanceSummary, null, 2), "utf8");

const preview = await workbook.render({ sheetName: sheet.name, range: `${targetAddress}1:${targetAddress}57`, scale: 2, format: "png" });
await fs.writeFile(`${outputDir}/fg_column_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(workbookPath);

console.log(JSON.stringify({
  workbookPath,
  outputDir,
  targetDate,
  targetColumn: targetAddress,
  updated: written.length,
  missing,
  last3Dates: resonanceSummary.last3Dates,
  innerOuterSameCount: innerOuterSame.length,
  tripleResonanceCount: tripleResonance.length,
  repeatedInnerOuterSame: resonanceSummary.repeatedInnerOuterSame.map(({ variety, count }) => ({ variety, count })),
  repeatedTripleResonance: resonanceSummary.repeatedTripleResonance.map(({ variety, count }) => ({ variety, count })),
}, null, 2));
