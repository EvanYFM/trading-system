import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-6.16-已更新.xlsx");
const outputDir = "output/main_trend_update_20260702_03";

const checks = [
  { date: "2026-07-02", serial: 46205, variety: "棕榈油" },
  { date: "2026-07-02", serial: 46205, variety: "锡" },
  { date: "2026-07-02", serial: 46205, variety: "纯碱" },
  { date: "2026-07-03", serial: 46206, variety: "棕榈油" },
  { date: "2026-07-03", serial: 46206, variety: "锡" },
  { date: "2026-07-03", serial: 46206, variety: "合成橡胶" },
  { date: "2026-07-03", serial: 46206, variety: "镍" },
];

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;
const header = values[1];

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const readBack = checks.map((check) => {
  const col = header.findIndex((value) => Number(value) === check.serial);
  const row = rowByVariety.get(check.variety);
  return {
    ...check,
    foundColumn: col >= 0,
    foundRow: row !== undefined,
    address: col >= 0 && row !== undefined ? sheet.getRangeByIndexes(row, col, 1, 1).address : "",
    value: col >= 0 && row !== undefined ? values[row][col] : null,
  };
});

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/readback_checks.json`, JSON.stringify(readBack, null, 2), "utf8");
console.log(JSON.stringify(readBack, null, 2));
