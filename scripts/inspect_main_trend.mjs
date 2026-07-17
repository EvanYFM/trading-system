import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/29266/Desktop/主力趋势.xlsx";
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const summary = await workbook.inspect({
  kind: "workbook,sheet,table",
  tableMaxRows: 12,
  tableMaxCols: 20,
  maxChars: 12000,
});
console.log(summary.ndjson);

const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 4000 });
console.log("SHEETS");
console.log(sheets.ndjson);

await fs.mkdir("output/main_trend_inspect", { recursive: true });
for (const name of workbook.worksheets.items.map((sheet) => sheet.name)) {
  try {
    const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
    await fs.writeFile(`output/main_trend_inspect/${name}.png`, new Uint8Array(await preview.arrayBuffer()));
    console.log(`rendered ${name}`);
  } catch (error) {
    console.log(`render failed ${name}: ${error.message}`);
  }
}
