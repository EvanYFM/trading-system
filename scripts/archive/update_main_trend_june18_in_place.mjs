import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-6.16-已更新.xlsx");
const outputDir = "output/main_trend_update_20260618";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;

const targetSerial = 46191; // 2026-06-18
const header = values[1];
const targetCol = header.findIndex((value) => Number(value) === targetSerial);
if (targetCol < 0) throw new Error("Could not find 2026-06-18 column.");

const targetAddress = sheet.getRangeByIndexes(0, targetCol, 1, 1).address.replace(/\d+$/, "");
if (targetAddress !== "EY") {
  throw new Error(`2026-06-18 is in ${targetAddress}, expected EY.`);
}

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const styles = {
  plusLight: { color: "F4B183" },
  plusDark: { color: "FF0000" },
  minusLight: { color: "92D050" },
  minusDark: { color: "00B050" },
};

const updates = new Map([
  ["玻璃", ["家人-", "内资-", "外资-"]],
  ["纯碱", ["家人-", "外资-"]],
  ["焦煤", ["家人-"]],
  ["燃油", ["家人-"]],
  ["生猪", ["家人-", "内资+"]],
  ["红枣", ["家人-", "内资-"]],
  ["烧碱", ["家人+", "内资-"]],
  ["鸡蛋", ["家人-", "内资-"]],
  ["铁矿石", ["内资-"]],
  ["PVC", ["内资-", "外资-"]],
  ["碳酸锂", ["内资-"]],
  ["菜油", ["内资-", "外资-"]],
  ["热卷", ["内资-", "外资-"]],
  ["螺纹钢", ["内资-", "外资-"]],
  ["锡", ["内资-"]],
  ["天然橡胶", ["内资-"]],
  ["棕榈油", ["外资-"]],
  ["豆一", ["外资-"]],
  ["菜粕", ["外资+"]],
  ["锌", ["外资+"]],
]);

const skipped = [
  { source: "五大机构第2条", reason: "图片只显示“继续加空”，未显示品种名" },
  { source: "五大机构第7条", reason: "图片只显示“继续加空”，未显示品种名" },
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

const written = [];
for (const [variety, tags] of updates.entries()) {
  const row = rowByVariety.get(variety);
  if (row === undefined) {
    written.push({ variety, status: "missing-row" });
    continue;
  }

  const target = sheet.getRangeByIndexes(row, targetCol, 1, 1);
  const style = chooseStyle(tags);
  target.values = [[tags.join("\n")]];
  target.format.wrapText = tags.length > 1;
  if (style) target.format.fill.color = style.color;
  written.push({
    variety,
    row1: row + 1,
    col1: targetCol + 1,
    address: `${targetAddress}${row + 1}`,
    value: tags.join("\n"),
    color: style?.color ?? "",
    status: "updated",
  });
}

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/written_cells.json`, JSON.stringify({ written, skipped }, null, 2), "utf8");

const preview = await workbook.render({ sheetName: sheet.name, range: "EY1:EY57", scale: 2, format: "png" });
await fs.writeFile(`${outputDir}/ey_column_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(workbookPath);

console.log(JSON.stringify({
  workbookPath,
  targetColumn: targetAddress,
  updated: written.filter((x) => x.status === "updated").length,
  missing: written.filter((x) => x.status !== "updated"),
  skipped,
}, null, 2));
