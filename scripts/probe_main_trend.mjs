import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/29266/Desktop/主力趋势.xlsx";
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItemAt(0);
const used = sheet.getUsedRange();
const values = used.values;

const targetSerial = 46177;
const header = values[1];
const targetIndex = header.findIndex((value) => Number(value) === targetSerial);
const nonEmptyHeaderIndexes = header
  .map((value, index) => ({ index, value }))
  .filter((item) => item.value !== null && item.value !== undefined && item.value !== "");
console.log(JSON.stringify({
  sheet: sheet.name,
  targetSerial,
  targetIndex,
  excelColumn1Based: targetIndex + 1,
  headerValue: header[targetIndex],
  lastHeaders: nonEmptyHeaderIndexes.slice(-12),
}, null, 2));

const rows = [];
for (let r = 2; r < values.length; r += 1) {
  if (values[r][1]) rows.push({ row1: r + 1, variety: String(values[r][1]).replace(/\n/g, " / "), valueAtTarget: targetIndex >= 0 ? (values[r][targetIndex] ?? "") : "" });
}
console.log(JSON.stringify(rows, null, 2));
