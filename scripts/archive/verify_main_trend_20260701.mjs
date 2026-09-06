import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const desktopDir = path.join(process.env.USERPROFILE ?? "C:/Users/29266", "Desktop");
const workbookPath = path.join(desktopDir, "主力趋势-6.16-已更新.xlsx");
const outputDir = "output/main_trend_update_20260701";
const targetSerial = 46204;

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange().values;
const targetCol = values[1].findIndex((value) => Number(value) === targetSerial);

const rowByVariety = new Map();
for (let r = 2; r < values.length; r += 1) {
  const variety = values[r][1];
  if (variety) rowByVariety.set(String(variety).split("\n")[0].trim(), r);
}

const checks = ["玻璃", "螺纹钢", "铝", "白糖", "花生", "PVC", "乙二醇"];
const readBack = checks.map((variety) => {
  const row = rowByVariety.get(variety);
  return {
    variety,
    address: sheet.getRangeByIndexes(row, targetCol, 1, 1).address,
    value: values[row][targetCol],
  };
});

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/readback_checks.json`, JSON.stringify(readBack, null, 2), "utf8");
console.log(JSON.stringify(readBack, null, 2));
