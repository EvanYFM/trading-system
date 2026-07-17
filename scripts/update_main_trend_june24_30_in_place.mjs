import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-6.16-已更新.xlsx");
const outputDir = "output/main_trend_update_20260624_20260630";

const styles = {
  plusLight: { color: "F4B183" },
  plusDark: { color: "FF0000" },
  minusLight: { color: "92D050" },
  minusDark: { color: "00B050" },
};

const dateUpdates = [
  {
    date: "2026-06-24",
    serial: 46197,
    expectedColumn: "FE",
    updates: new Map([
      ["甲醇", ["家人-", "内资-"]],
      ["红枣", ["家人-", "内资-"]],
      ["烧碱", ["家人-", "内资-"]],
      ["鸡蛋", ["家人+", "内资+"]],
      ["银", ["家人+"]],
      ["纯碱", ["家人-", "内资-", "外资-"]],
      ["玻璃", ["家人+", "内资+", "外资-"]],
      ["燃油", ["家人+", "内资+"]],
      ["生猪", ["家人+", "内资+"]],
      ["纸浆", ["内资-", "外资-"]],
      ["铝", ["内资-", "外资-"]],
      ["苯乙烯", ["内资-", "外资-"]],
      ["乙二醇", ["内资-"]],
      ["铜", ["内资-"]],
      ["锌", ["内资-"]],
      ["沥青", ["内资+"]],
      ["碳酸锂", ["内资+"]],
      ["PVC", ["内资+", "外资+"]],
      ["焦煤", ["内资+"]],
      ["锰硅", ["外资-"]],
      ["硅铁", ["外资-"]],
      ["螺纹钢", ["外资-"]],
      ["白糖", ["外资-"]],
      ["豆油", ["外资+"]],
      ["豆粕", ["外资+"]],
      ["菜粕", ["外资+"]],
      ["豆一", ["外资+"]],
    ]),
  },
  {
    date: "2026-06-25",
    serial: 46198,
    expectedColumn: "FF",
    updates: new Map([
      ["银", ["家人-"]],
      ["红枣", ["家人-", "内资-"]],
      ["燃油", ["家人-"]],
      ["焦煤", ["家人-"]],
      ["纸浆", ["家人-", "内资-", "外资-"]],
      ["氧化铝", ["家人-"]],
      ["工业硅", ["家人-"]],
      ["白糖", ["内资-", "外资-"]],
      ["纯碱", ["内资-", "外资-"]],
      ["铝", ["内资-", "外资-"]],
      ["合成橡胶", ["内资-"]],
      ["天然橡胶", ["内资-"]],
      ["棕榈油", ["内资-", "外资-"]],
      ["碳酸锂", ["内资-"]],
      ["金", ["内资-"]],
      ["锰硅", ["外资-"]],
      ["硅铁", ["外资-"]],
      ["螺纹钢", ["外资-"]],
      ["热卷", ["外资-"]],
      ["PVC", ["外资-"]],
      ["菜粕", ["外资-"]],
      ["菜油", ["外资-"]],
      ["铁矿石", ["外资-"]],
      ["20号胶", ["外资-"]],
    ]),
  },
  {
    date: "2026-06-26",
    serial: 46199,
    expectedColumn: "FG",
    updates: new Map([
      ["纯碱", ["家人-", "内资-", "外资-"]],
      ["银", ["家人-"]],
      ["红枣", ["家人-", "内资-"]],
      ["烧碱", ["家人-", "内资-"]],
      ["氧化铝", ["家人-"]],
      ["燃油", ["家人-", "内资-"]],
      ["鸡蛋", ["家人-", "内资-"]],
      ["生猪", ["家人+", "内资+"]],
      ["PVC", ["内资-", "外资-"]],
      ["纸浆", ["内资-", "外资-"]],
      ["白糖", ["内资-", "外资-"]],
      ["苯乙烯", ["内资-", "外资-"]],
      ["合成橡胶", ["内资-"]],
      ["玻璃", ["内资-", "外资-"]],
      ["锌", ["内资-", "外资-"]],
      ["碳酸锂", ["内资-"]],
      ["苹果", ["内资+"]],
      ["豆一", ["内资+", "外资+"]],
      ["菜粕", ["内资+"]],
      ["铁矿石", ["内资+"]],
      ["锰硅", ["外资-"]],
      ["硅铁", ["外资-"]],
      ["螺纹钢", ["外资-"]],
      ["塑料", ["外资-"]],
      ["豆油", ["外资+"]],
      ["菜油", ["外资+"]],
      ["豆粕", ["外资+"]],
      ["铝", ["外资+"]],
    ]),
  },
  {
    date: "2026-06-29",
    serial: 46202,
    expectedColumn: "FJ",
    updates: new Map([
      ["生猪", ["家人+", "内资+"]],
      ["鸡蛋", ["家人+", "内资+"]],
      ["合成橡胶", ["家人+", "内资+"]],
      ["玻璃", ["家人+", "内资+"]],
      ["纯碱", ["家人+", "内资+"]],
      ["焦煤", ["家人+", "内资+"]],
      ["银", ["家人-"]],
      ["铜", ["内资+", "外资+"]],
      ["锌", ["内资+"]],
      ["纸浆", ["内资+"]],
      ["白糖", ["内资+", "外资-"]],
      ["花生", ["内资+", "外资+"]],
      ["PP", ["内资+"]],
      ["PTA", ["内资+", "外资+"]],
      ["苯乙烯", ["内资+"]],
      ["乙二醇", ["内资+"]],
      ["PVC", ["内资-", "外资-"]],
      ["菜油", ["外资+"]],
      ["豆油", ["外资+"]],
      ["豆粕", ["外资+"]],
      ["菜粕", ["外资+"]],
      ["硅铁", ["外资+"]],
    ]),
  },
  {
    date: "2026-06-30",
    serial: 46203,
    expectedColumn: "FK",
    notes: [
      "沪铝在机构区同时出现小幅加多和加空，外资为加空；本次按合并偏空写入内资-/外资-。",
    ],
    updates: new Map([
      ["鸡蛋", ["家人+", "内资+"]],
      ["烧碱", ["家人-", "内资-"]],
      ["焦煤", ["家人-", "内资-"]],
      ["铝", ["内资-", "外资-"]],
      ["碳酸锂", ["内资+"]],
      ["天然橡胶", ["内资+"]],
      ["花生", ["内资+", "外资+"]],
      ["PVC", ["内资+", "外资-"]],
      ["纯碱", ["内资-", "外资-"]],
      ["玻璃", ["外资-"]],
      ["镍", ["外资-"]],
      ["豆一", ["外资-"]],
      ["菜粕", ["外资-"]],
      ["豆粕", ["外资-"]],
      ["螺纹钢", ["外资-"]],
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

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;
const header = values[1];

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const written = [];
const missing = [];
const notes = [];

for (const dateConfig of dateUpdates) {
  const targetCol = header.findIndex((value) => Number(value) === dateConfig.serial);
  if (targetCol < 0) throw new Error(`Could not find ${dateConfig.date} column.`);

  const targetAddress = sheet.getRangeByIndexes(0, targetCol, 1, 1).address.replace(/\d+$/, "");
  if (targetAddress !== dateConfig.expectedColumn) {
    throw new Error(`${dateConfig.date} is in ${targetAddress}, expected ${dateConfig.expectedColumn}.`);
  }

  for (const note of dateConfig.notes ?? []) {
    notes.push({ date: dateConfig.date, note });
  }

  for (const [variety, tags] of dateConfig.updates.entries()) {
    const row = rowByVariety.get(variety);
    if (row === undefined) {
      missing.push({ date: dateConfig.date, variety, reason: "missing-row" });
      continue;
    }

    const target = sheet.getRangeByIndexes(row, targetCol, 1, 1);
    const style = chooseStyle(tags);
    target.values = [[tags.join("\n")]];
    target.format.wrapText = tags.length > 1;
    if (style) target.format.fill.color = style.color;
    written.push({
      date: dateConfig.date,
      variety,
      row1: row + 1,
      col1: targetCol + 1,
      address: `${targetAddress}${row + 1}`,
      value: tags.join("\n"),
      color: style?.color ?? "",
      status: "updated",
    });
  }
}

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(
  `${outputDir}/written_cells.json`,
  JSON.stringify({ workbookPath, written, missing, notes }, null, 2),
  "utf8",
);

const preview = await workbook.render({
  sheetName: sheet.name,
  range: "FE1:FK57",
  scale: 2,
  format: "png",
});
await fs.writeFile(`${outputDir}/fe_fk_columns_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(workbookPath);

console.log(JSON.stringify({
  workbookPath,
  outputDir,
  updated: written.length,
  missing,
  notes,
}, null, 2));
