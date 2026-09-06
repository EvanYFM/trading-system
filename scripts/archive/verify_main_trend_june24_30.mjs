import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-6.16-已更新.xlsx");
const outputDir = "output/main_trend_update_20260624_20260630";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;

const serials = [46197, 46198, 46199, 46202, 46203];
const colBySerial = new Map();
for (let c = 0; c < values[1].length; c += 1) {
  const serial = Number(values[1][c]);
  if (serials.includes(serial)) colBySerial.set(serial, c);
}

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const checks = [
  [46197, "PVC"],
  [46197, "纯碱"],
  [46198, "纸浆"],
  [46199, "纯碱"],
  [46202, "铜"],
  [46202, "PVC"],
  [46203, "鸡蛋"],
  [46203, "铝"],
];

const readBack = checks.map(([serial, variety]) => {
  const row = rowByVariety.get(variety);
  const col = colBySerial.get(serial);
  return {
    serial,
    variety,
    address: sheet.getRangeByIndexes(row, col, 1, 1).address,
    value: values[row][col],
  };
});

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/readback_checks.json`, JSON.stringify(readBack, null, 2), "utf8");
console.log(JSON.stringify(readBack, null, 2));
